import os, re
from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_script import Manager
from flask_cors import CORS
from models import db, Services, Profile, Communes, Availability, Ratings, User, Requests, Specialty
from flask_bcrypt import Bcrypt
from datetime import date, datetime, time, timedelta
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from sqlalchemy.sql import text
import datetime
from flask_mail import Mail, Message

BASEDIR = os.path.abspath(os.path.dirname(__file__))

key = os.getenv("API_JWT_KEY")
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASEDIR, 'te_ayudo.db')
app.config["DEBUG"] = True
app.config["ENV"] = "development"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = 'secret-key'
app.config["JWT_SECRET_KEY"] = key
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'teayudogeeks@gmail.com'
app.config['MAIL_PASSWORD'] = 'ymagqkgwnsecmvnt'

db.init_app(app)
Migrate(app, db)
manager = Manager(app)
#manager.add_command("db", MigrateCommand)
CORS(app)
jwt = JWTManager(app)
bcrypt = Bcrypt(app)
mail = Mail(app)


@app.route('/mail')
def send_mail():
    msg = Message("Hola un gusto saludarte desde 'TeAyudo?'", sender="teayudogeeks@gmail.com")
    msg.recipients = request.json.get("recipients")
    msg.body ="Tenemos el agrado de informar que su cuenta se ha creado en la aplicación 'TeAyudo?'"
    mail.send(msg)
    return jsonify("El correo se ha enviado exitosamente."), 200


@app.route("/")
def main():
    return render_template('index.html')

#Cesar inicio
#login usuario
@app.route("/user/login", methods=["POST"])
def login():
    email = request.json.get("email")
    password = request.json.get("password")
    #validacion al informar email y password
    if email == "":
        return jsonify("Debe informar su email."), 400
    if password == "":
        return jsonify("Debe informar su contraseña."), 400            

    #Regular expression that checks a valid email
    ereg = '^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
    #Regular expression that checks a valid password
    preg = '^.*(?=.{4,})(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).*$'
    user = User()
    #Checking email     
    if (re.search(ereg,request.json.get("email"))):
        user.email = request.json.get("email")               
    else:
        return jsonify("Formato de email erróneo."), 400
    #Checking password
    if (re.search(preg,request.json.get('password'))):
        pw_hash = bcrypt.generate_password_hash(request.json.get("password"))
        user.password = pw_hash
    else:
        return jsonify("Formato de contraseña errónea."), 400
    #valida que el usario exista    
    user = User.query.filter_by(email=email).first()
    profile = Profile.query.filter_by(id_user=request.json.get("email")).first()
    
    if user is None:             
        return jsonify("Usuario no existe."), 404
    commune_names=[]
    name_specialty=[]
    if profile.role != "client":
        communes = Communes.query.filter_by(email=email).all()
        commune_names=[]
        for commune in communes:
            commune_names.append(commune.name_commune)
        
        specialists=Specialty.query.filter_by(id_user=email).all()
        name_specialty=[]
        for specialty in specialists:
            name_specialty.append(specialty.name_specialty)

    if bcrypt.check_password_hash(user.password, password): #retorna booleano
        access_token =create_access_token(identity=email)
        return jsonify({
            "user": user.serialize_all_fields(),     
            "profile" : profile.serialize_all_fields(),
            "access_token": access_token,
            "communes": commune_names,
            "specialists": name_specialty
        }),200
    else:
        return jsonify("Ha ingresado mal la contraseña."), 400


#Editar un usuario
@app.route('/user/profile/<int:id>', methods=['PUT'])
@jwt_required()
def get_profile_id(id):
    if request.method == 'PUT':
        if id is not None:
            profile = Profile.query.filter_by(id=id).first()
            if profile is None :
                return jsonify("Usuario no existe."), 404
            user = User.query.filter_by(id=profile.id).first()
            #Para la primera etapa en name_region sera por defecto Region Metropolitana
            region= "Region Metropolitana"           
            #Regular expression that checks a valid phone
            phonereg = '^(56)?(\s?)(0?9)(\s?)[9876543]\d{7}$'
            #Regular expression that checks a valid password
            preg = '^.*(?=.{4,})(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).*$'
            #Checking password
            if (re.search(preg,request.json.get('password'))):
                pw_hash = bcrypt.generate_password_hash(request.json.get("password"))
                user.password = pw_hash
            else:
                return jsonify("Formato de contraseña errónea."), 400
            #Checking phone
            if (re.search(phonereg,str(request.json.get('phone')))):
                user.phone = request.json.get("phone")
            else:
                return jsonify("Formato de teléfono erróneo."), 400          
           
            user.name_commune = request.json.get("name_commune")
            user.address = request.json.get("address")
            profile.id_profile = request.json.get("id_profile")
            profile.role = request.json.get("role")
            profile.phone = request.json.get("phone")
            profile.question = request.json.get("question")
            profile.answer = request.json.get("answer")
            #validacion entrada
            if user.name_commune == "":
                return jsonify("Debe informar su comuna de residencia."), 400  
            if user.address == "":
                return jsonify("Debe informar su dirección."), 400                               
            #busca en disponibilidad si existe el usuario
            #para cliente que quiere ser especialista le crea la disponibilidad al editar
            availability = Availability.query.filter_by(id_user=profile.id_user).first()
            attetion_communes=[]
            specialties=[]
            if profile.role != "client":   
                if availability is None:                
                    for day in range(15):
                        availability = Availability()
                        date = datetime.date.today () + timedelta(days=day)
                        availability.date=date
                        availability.morning = True
                        availability.afternoon = True
                        availability.evening = True
                        availability.id_user = profile.id_user
                        db.session.add(availability)
                Communes.query.filter_by(
                    email = (user.email)
                ).delete(synchronize_session=False)         
                profile.experience = request.json.get("experience")
                attetion_communes = request.json.get("communes")
                for name_commune in attetion_communes:
                    communes=Communes()
                    communes.name_commune=name_commune 
                    communes.email = user.email
                    communes.name_region = region
                    db.session.add(communes)                
                Specialty.query.filter_by(
                    id_user = (user.email)
                ).delete(synchronize_session=False)
                specialties = request.json.get("name_specialty")
                #specialties = ["pintor", "carpintero", "electricista"]
                for name_specialty in specialties:
                    specialty=Specialty ()
                    specialty.name_specialty=name_specialty
                    specialty.id_user = user.email
                    db.session.add(specialty)
                
                db.session.query(Profile).filter_by(
                    id=id
                    ).update({Profile.id_communes:user.email}, synchronize_session = False)

            db.session.commit()
            if bcrypt.check_password_hash(user.password,request.json.get("password")): #retorna booleano
                access_token =create_access_token(identity=user.email)
                return jsonify({
                    "user": user.serialize_all_fields(),     
                    "profile" : profile.serialize_all_fields(),
                    "access_token": access_token,
                    "communes": attetion_communes,
                    "specialists": specialties
                }),200
        else:
            return jsonify("Usuario no existe."), 404

#Crear un nuevo usuario          
@app.route('/user/profile', methods=["GET", "POST"])
def get_profile():
    if request.method == "POST":
        #valida que el usuario ya exista como cliente o especialista
        email = request.json.get("email")
        rut_reg =request.json.get("rut")
        user = User.query.filter_by(email=email).first() 
        rut_user = User.query.filter_by(rut=rut_reg).first()    
    
        if user != None:             
            return jsonify("Usted ya existe como cliente. Ingrese a su sesión y seleccione editar perfil."), 404

        if rut_user != None:             
            return jsonify("El rut ingresado ya existe en nuestros registros."), 404

        #valida que venga informado el email
        if email == "":
            return jsonify("Debe informar su email."), 400                  
        #Para la primera etapa en name_region sera por defecto Region Metropolitana
        region= "Region Metropolitana"
        #Regular expression that checks a valid email
        ereg = '^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$'
        #Regular expression that checks a valid password
        preg = '^.*(?=.{4,})(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).*$'
        #Regular expression that checks a valid phone
        phonereg = '^(56)?(\s?)(0?9)(\s?)[9876543]\d{7}$'
        #Regular expression that checks a valid rut
        rut = '^[1-9]{1}[0-9]{6,7}-[0-9kK]{1}$'
        user = User() 

        #Checking email
        if (re.search(ereg,request.json.get("email"))):
            user.email = request.json.get("email")
        else:
            return jsonify("Formato de email erróneo."), 400
        #Checking password
        if (re.search(preg,request.json.get('password'))):
            pw_hash = bcrypt.generate_password_hash(request.json.get("password"))
            user.password = pw_hash
        else:
            return jsonify("Formato de contraseña errónea."), 400
        #Checking rut
        if (re.search(rut,request.json.get('rut'))):
            user.rut = request.json.get("rut")
        else:
            return jsonify("Formato de RUT erróneo."), 400            
        #Checking phone
        if (re.search(phonereg,str(request.json.get('phone')))):
            user.phone = request.json.get("phone")
        else:
            return jsonify("Formato de teléfono erróneo."), 400

        user.full_name = request.json.get("full_name")     
        user.last_name = request.json.get("last_name")
        user.address = request.json.get("address")
        user.name_commune = request.json.get("name_commune")
        #validacion campos de entrada
        if user.full_name == "":
            return jsonify("Debe informar su nombre."), 400   
        if user.last_name == "":
            return jsonify("Debe informar su apellido."), 400  
        if user.address == "":
            return jsonify("Debe informar su dirección."), 400  
        if user.name_commune == "":
            return jsonify("Debe informar su comuna de residencia."), 400                                              
        db.session.add(user)

        profile = Profile()
        profile.role = request.json.get("role")
        profile.question = request.json.get("question")
        profile.answer = request.json.get("answer")
        profile.id_user = request.json.get("email")

        if profile.role != "client":
            profile.experience = request.json.get("experience")
            profile.id_communes= request.json.get("email")
            for day in range(15):
                availability = Availability()
                date = datetime.date.today () + timedelta(days=day)
                availability.date=date
                availability.morning = True
                availability.afternoon = True
                availability.evening = True
                availability.id_user = request.json.get("email")
                db.session.add(availability)
            attetion_communes = request.json.get("communes")
            for name_commune in attetion_communes:
                communes=Communes()
                communes.name_commune=name_commune
                communes.email = request.json.get("email")
                communes.name_region = region
                db.session.add(communes)
            specialties = request.json.get("name_specialty")
            for name_specialty in specialties:
                specialty=Specialty ()
                specialty.name_specialty=name_specialty
                specialty.id_user = request.json.get("email")
                db.session.add(specialty)
        db.session.add(profile)
        db.session.commit()

        return jsonify({
            'user':user.serialize_all_fields(),
            'profile':profile.serialize_all_fields()
            }), 200

    if request.method == "GET":
        profiles = Profile.query.all()
        profiles = list(map(lambda profile: profile.serialize_strict(), profiles))
        return jsonify(profiles), 200

#Devuelve por defecto lista de carpinteros disponibles para mañana
@app.route("/service/default/<int:id>", methods=["GET"])
@jwt_required()
def get_services_default(id):
    if request.method == "GET":
        if id is not None:
                specialties = Specialty.query.all()
                answer = []
                date = datetime.date.today() + timedelta(days=1)
                date=date.strftime("%Y-%m-%d %H:%M:%S.%S%S%S")
                counter = 0
                communes = Communes.query.all() 
                
                for specialty in specialties:
                    for commune in communes:
                        profile = Profile.query.filter_by(id_user=specialty.id_user, id_communes = commune.email).first()
                        availability = Availability.query.filter_by(date=date, id_user=specialty.id_user).first()
                        user=User.query.filter_by(email=specialty.id_user).first()
                        #if user !=None and user.id == id:
                        # user = None
                        if user !=None and availability != None and profile != None and user.id != id:
                            counter = counter+1
                            answer.append({
                                'specialty':specialty.serialize_all_fields(), 
                                'user':user.serialize_all_fields(), 
                                'availability': availability.serialize_all_fields(),
                                'profile': profile.serialize_all_fields(),
                                'commune': commune.serialize_all_fields()
                                })
                if counter > 0:    
                    return jsonify(answer), 200
                else:
                    return jsonify("No hay especialistas disponibles."), 200

#Devuelve lista de especialistas disponibles
@app.route("/service/<int:id>", methods=["POST"])
@jwt_required()
def get_services(id):
    if request.method == "POST":
        if id is not None:
                speciality = request.json.get("name_specialty")
                commun = request.json.get("name_commune")
                specialties = Specialty.query.filter_by(name_specialty=speciality).all()
                communes = Communes.query.filter_by(name_commune=commun).all()
                answer = []
                date = request.json.get("date")
                date = datetime.datetime.strptime(date,'%Y-%m-%d %H:%M:%S.%f')
                #validaciones de entrada
                if speciality == "":
                    specialties = Specialty.query.all()
                if commun == "":
                    communes = Communes.query.all()       
                if date == "":
                    return jsonify("Debe informar la fecha cuando se realizará el trabajo."), 400       
                counter = 0
                for specialty in specialties:
                    for commune in communes:
                        profile = Profile.query.filter_by(id_user=specialty.id_user, id_communes = commune.email).first()
                    
                        availability= None
                        if request.json.get("morning") == True and request.json.get("afternoon") == False and request.json.get("evening") == False:
                            availability = Availability.query.filter_by(date=date, morning=True, id_user=specialty.id_user).first()
                    
                        elif request.json.get("morning") == False and request.json.get("afternoon") == True and request.json.get("evening") == False:
                            availability = Availability.query.filter_by(date=date, afternoon=True, id_user=specialty.id_user).first()
                    
                        elif request.json.get("morning") == False and request.json.get("afternoon") == False and request.json.get("evening") == True:
                            availability = Availability.query.filter_by(date=date, evening=True, id_user=specialty.id_user).first()
                        
                        elif request.json.get("morning") == False and request.json.get("afternoon") == False and request.json.get("evening") == False:
                            availability = Availability.query.filter_by(date=date, id_user=specialty.id_user).first()
                
                        user=User.query.filter_by(email=specialty.id_user).first()
                    
                        if user !=None and availability != None and profile != None and user.id != id:
                            counter = counter+1
                            answer.append({
                                'specialty':specialty.serialize_all_fields(), 
                                'user':user.serialize_all_fields(), 
                                'availability': availability.serialize_all_fields(),
                                'profile': profile.serialize_all_fields(),
                                'commune': commune.serialize_all_fields()
                                })
                if counter > 0:    
                    return jsonify(answer), 200
                else:
                    return jsonify("No hay especialistas disponibles backend"), 200
#Cesar fin

#@app.route("/availability", methods=["GET", "POST"])
#def get_availability():
#    if request.method == "POST":
#        availability = Availability()
#        availability.id = request.json.get("id")             
#        availability.date = request.json.get("date")
    #     db.session.add(availability)
    #     db.session.commit()
    #     return jsonify(availability.serialize_all_fields()), 200

    # if request.method == "GET":
    #     availabilitys = Availability.query.all()
    #     availabilitys = list(map(lambda availability: availability.serialize_strict(), availabilitys))
    #     return jsonify(availabilitys), 200


# @app.route("/ratings", methods=["GET", "POST"])
# def get_ratings():
#     if request.method == "POST":
#         rating = Ratings()
#         rating.id = request.json.get("id")             
#         rating.rating = request.json.get("rating")
#         db.session.add(rating)
#         db.session.commit()
#         return jsonify(rating.serialize_all_fields()), 200

#     if request.method == "GET":
#         ratings = Ratings.query.all()
#         ratings = list(map(lambda rating: rating.serialize_strict(), ratings))
#         return jsonify(ratings), 200

#Crear una solicitud
@app.route("/user/requests", methods=["GET", "POST"])
@jwt_required()
def get_requests():
    if request.method == "POST":
        id = request.json.get("id")
        if id is None:
            return jsonify("Cliente no viene informado. Por favor ingrese nuevamente a la aplicacion."), 404
        if id is not None:
            user = User.query.filter_by(id=id).first()
            if user is None :
                return jsonify("Cliente no viene informado. Por favor ingrese nuevamente a la aplicacion."), 404
        request_status ="pendiente"
        hour = request.json.get("hour")
        id_profile = request.json.get("id_profile")
        #valida que venga informada la fecha
        if request.json.get("date") is None or request.json.get("date") == '':
            return jsonify("La fecha no viene informada. Por favor realizar nuevamente la solicitud."), 404         
        date = request.json.get("date")
        date = datetime.datetime.strptime(date,'%Y-%m-%d %H:%M:%S.%f')
        #valida que venga informada la especialidad
        if request.json.get("name_specialty") is None or request.json.get("name_specialty") == '':
            return jsonify("La especialidad no viene informada. Por favor realizar nuevamente la solicitud."), 404
        #valida que venga informada la comuna
        if request.json.get("name_commune") is None or request.json.get("name_commune") == "":
            return jsonify("La comuna no viene informada. Por favor realizar nuevamente la solicitud."), 404
        #valida que venga informado el horario
        if hour is None or hour == '':
            return jsonify("El horario no viene informado. Por favor realizar nuevamente la solicitud."), 404
        #valida que venga informada la dirección
        if request.json.get("address") is None or request.json.get("address") == '':
            return jsonify("La direccion no viene informada. Por favor realizar nuevamente la solicitud."), 404
        #valida que el especialista venga informado
        if id_profile is None or id_profile == '':
            return jsonify("El especialista no viene informado. Por favor realizar nuevamente la solicitud."), 404
        #valida que el cliente y el especialista sean distintos
        if user.email == id_profile:
            return jsonify("No puede realizar una solicitud para usted mismo."), 404
        #validar el horario si ya está seleccionado
        validate_time=Availability.query.filter_by(id_user=id_profile,date=request.json.get("date")).first()
        if hour == 'morning' and validate_time.morning == False:
            return jsonify("El horario 08:00 - 11:00 ya está tomado por el especialista. Por favor elija otro horario."), 404
        elif hour == 'afternoon' and validate_time.afternoon == False:
            return jsonify("El horario 11:00 - 14:00 ya está tomado por el especialista. Por favor elija otro horario."), 404
        elif hour == 'evening' and validate_time.evening == False:
            return jsonify("El horario 14:00 - 17:00 ya está tomado por el especialista. Por favor elija otro horario."), 404            
        profile = User.query.filter_by(email=id_profile).first()
        requests = Requests()
        requests.name_specialty = request.json.get("name_specialty")
        requests.name_commune = request.json.get("name_commune")
        requests.request_status = request_status
        requests.full_name_user = user.full_name
        requests.last_name_user = user.last_name
        requests.contact_phone_user = user.phone
        requests.full_name_profile = profile.full_name
        requests.last_name_profile = profile.last_name
        requests.contact_phone_profile = profile.phone
        requests.address = request.json.get("address")
        requests.date = date
        requests.hour = hour
        requests.id_user = user.email
        requests.id_profile = id_profile
        db.session.add(requests)                 
        #busca el registro en Availability segun el especialista y la fecha
        db.session.query(Availability).filter_by(
            id_user=id_profile,date=request.json.get("date")
            ).first()
        if hour == 'morning':
            hourformat= "08:00 - 11:00"
            morning = False
            afternoon = Availability.afternoon
            evening = Availability.evening
        elif hour == 'afternoon':
            hourformat= "11:00 - 14:00"
            morning= Availability.morning
            afternoon = False
            evening = Availability.evening
        elif hour == 'evening':
            hourformat= "14:00 - 17:00"
            morning = Availability.morning
            afternoon = Availability.afternoon
            evening =False                        
        #realiza un update a la tabla Availability para modificar a False el momento del dia seleccionado 
        db.session.query(Availability).filter_by(
            id_user=id_profile,date=request.json.get("date")
            ).update({Availability.morning:morning,Availability.afternoon:afternoon,Availability.evening:evening}, synchronize_session = False)
        #Envia correo al especialista de la solicitud generada
        msg = Message("Hola " + profile.full_name+ " " + profile.last_name + " se ha Agendado una solicitud en 'TeAyudo?'", sender="teayudogeeks@gmail.com", recipients=[id_profile])
        msg.body =("Tenemos el agrado de comuniarle que se ha generado una solicitud para la especialidad: " + request.json.get("name_specialty") + ". Cliente: " +user.full_name+ " " +user.last_name + ". Contacto: " +str(user.phone)+ ". Fecha: " +str(date)+ ". Horario: " +hourformat+ ".")
        #msg.html= "<button to='/Login' className='btn btn-block btn-ta1 text-white' href='#' role='button'>Ingresa Aquí</button>"
        mail.send(msg)
        db.session.commit()
        return jsonify({'requests':requests.serialize_all_fields()}), 200

    if request.method == "GET":
        requests = Requests.query.all()
        requests = list(map(lambda request: request.serialize_strict(), requests))
        return jsonify(requests), 200

@app.route("/user/requests_client/<int:id>", methods=["GET"])
@jwt_required()
def get_requests_client(id):
    if request.method == "GET":
        if id is None or id == '':
            return jsonify("Usuario no viene informado."), 404
        else:
            if id is not None:
                profile = Profile.query.filter_by(id=id).first()
                if profile is None:
                    return jsonify("Usuario no existe."), 404
                user = User.query.filter_by(id=id).first() 
                requests_all = Requests.query.all()
                answer = []
                request_client= Requests.query.filter_by(id_user=user.email).all()
                #trae las solicitudes del cliente segun el id informado
                if request_client > []:
                    for requests_all in request_client:                
                        answer.append({
                                    'requests':requests_all.serialize_all_fields()
                                    })
                    return jsonify(answer), 200   
                else:
                    return jsonify("Usted no tiene solicitudes creadas."), 200


@app.route("/user/cancel_request", methods=['PUT'])
@jwt_required()
def get_cancel_request():
    if request.method == 'PUT':         
        id = request.json.get("id")
        request_cancel ="cancelada"
        if id is None or id == '':
            return jsonify("Solicitud no viene informada."), 404
        else:
            if id is not None:
                requests = Requests.query.filter_by(id=id).first()
                db.session.query(Availability).filter_by(
                    id_user=requests.id_profile,date=requests.date
                    ).first()
                if requests.hour == 'morning':
                    morning = True
                    afternoon = Availability.afternoon
                    evening = Availability.evening
                elif requests.hour == 'afternoon':
                    morning= Availability.morning
                    afternoon = True
                    evening = Availability.evening
                elif requests.hour == 'evening':
                    morning = Availability.morning
                    afternoon = Availability.afternoon
                    evening =True

                if requests is None:
                    return jsonify("Solicitud no existe."), 404
                if requests.request_status == 'pendiente' or requests.request_status == 'aceptada':
                    #realiza un update a la tabla Requests para modificar a Cancelada el status de la solicitud 
                    db.session.query(Requests).filter_by(
                        id=id
                        ).update({Requests.request_status:request_cancel}, synchronize_session = False)
                    #realiza un update a la tabla Availability para modificar a True el momento del dia cancelado 
                    db.session.query(Availability).filter_by(
                        id_user=requests.id_profile,date=requests.date
                        ).update({Availability.morning:morning,Availability.afternoon:afternoon,Availability.evening:evening}, synchronize_session = False)
                    #Envia correo al especialista de la solicitud cancelada
                    msg = Message("Hola se ha Cancelado una solicitud en 'TeAyudo?'", sender="teayudogeeks@gmail.com", recipients=[requests.id_profile, requests.id_user])
                    msg.body =("Buen día. 'TeAyudo?' informa que se ha Cancelado una solicitud para la especialidad: " + requests.name_specialty + ". Cliente: " +requests.full_name_user+ " " +requests.last_name_user + ". Contacto: " +str(requests.contact_phone_user)+ ". Especialista: " +requests.full_name_profile+ " " +requests.last_name_profile + ". Contacto: " +str(requests.contact_phone_profile) + ". Fecha: " +str(requests.date)+ ".")
                    mail.send(msg)                    
                    db.session.commit()
                    return jsonify("Su solicitud ha sido cancelada."), 200
                elif requests.request_status == 'resuelta':
                    return jsonify("La solicitud ya está resuelta."), 404
                elif requests.request_status == 'cancelada':
                    return jsonify("La solicitud ya está cancelada."), 404


@app.route("/user/close_request", methods=['PUT'])
@jwt_required()
def get_close_request():
    if request.method == 'PUT':         
        id = request.json.get("id")
        request_close ="resuelta"
        if id is None or id == '':
            return jsonify("Solicitud no viene informada."), 404
        else:
            if id is not None:
                requests = Requests.query.filter_by(id=id).first()
                if requests is None:
                    return jsonify("Solicitud no existe."), 404
                if requests.request_status == 'pendiente':
                    return jsonify("Las solicitudes pendientes solo se pueden aceptar o cancelar."), 404
                elif requests.request_status == 'aceptada':
                #realiza un update a la tabla Requests para modificar a Resuelta el status de la solicitud     
                    db.session.query(Requests).filter_by(
                        id=id
                        ).update({Requests.request_status:request_close}, synchronize_session = False)
                    db.session.commit()
                    return jsonify("Su solicitud ha sido resuelta."), 200
                elif requests.request_status == 'resuelta':
                    return jsonify("La solicitud ya está resuelta."), 404
                elif requests.request_status == 'cancelada':
                    return jsonify("La solicitud ya está cancelada."), 404


@app.route("/user/acept_request", methods=['PUT'])
@jwt_required()
def get_acept_request():
    if request.method == 'PUT':         
        id = request.json.get("id")
        request_acept ="aceptada"
        if id is None or id == '':
            return jsonify("Solicitud no viene informada."), 404
        else:
            if id is not None:
                requests = Requests.query.filter_by(id=id).first()
                if requests is None:
                    return jsonify("Solicitud no existe."), 404
                if requests.request_status == 'pendiente':
                    db.session.query(Requests).filter_by(
                        id=id
                        ).update({Requests.request_status:request_acept}, synchronize_session = False)
                    #Envia correo al especialista de la solicitud aceptada
                    msg = Message("Hola " + requests.full_name_user+ " " + requests.last_name_user + " se ha Aceptado una solicitud en 'TeAyudo?'", sender="teayudogeeks@gmail.com", recipients=[requests.id_user])
                    msg.body =("Buen día. 'TeAyudo?' informa que se ha Aceptado una solicitud para la especialidad: " + requests.name_specialty + ". Especialista: " +requests.full_name_profile+ " " +requests.last_name_profile + ". Contacto: " +str(requests.contact_phone_profile)+ ". Fecha: " +str(requests.date)+ ".")
                    mail.send(msg)
                    db.session.commit()                    
                    return jsonify("Su solicitud ha sido aceptada."), 200
                elif requests.request_status == 'aceptada':
                    return jsonify("Las solicitudes ya está aceptada."), 404                    
                elif requests.request_status == 'resuelta':
                    return jsonify("La solicitud ya está resuelta."), 404
                elif requests.request_status == 'cancelada':
                    return jsonify("La solicitud ya está cancelada."), 404
                    

@app.route("/user/requests_specialist/<int:id>", methods=["GET"])
@jwt_required()
def get_requests_specialist(id):
    if request.method == "GET":
        if id is None or id == '':
            return jsonify("Usuario no viene informado."), 404
        else:
            if id is not None:
                profile = Profile.query.filter_by(id=id).first()
                if profile is None:
                    return jsonify("Usuario no existe."), 404
                user = User.query.filter_by(id=id).first() 
                requests_all = Requests.query.all()
                answer = []
                request_client= Requests.query.filter_by(id_profile=user.email).all()
                #trae las solicitudes del cliente segun el id informado
                if request_client > []:
                    for requests_all in request_client:                
                        answer.append({
                                    'requests':requests_all.serialize_all_fields()
                                    })
                    return jsonify(answer), 200   
                else:
                    return jsonify("Usted no tiene solicitudes creadas."), 200


if __name__ == "__main__":
    manager.run()





