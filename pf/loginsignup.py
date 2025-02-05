from pf import app
from flask import redirect, request,make_response
from flask_cors import CORS, cross_origin
from datetime import datetime
from flask import jsonify

import firebase_admin
from firebase_admin import credentials
from firebase_admin import auth
from pf import dbfunc as db
from pf import pancard_verify as panv
from pf import jwtdecodenoverify as jwtnoverify

import psycopg2
import jwt
import requests
import json
import os


@app.route('/natkeyss',methods=['GET','POST','OPTIONS'])
def natkeyss():
#This is called by setjws service
    if request.method=='OPTIONS':
        print("inside SETNATKEY options")
        return(jsonify('inside SATNATKEY options'),200)

    elif request.method=='POST':
        print('insider GET of natkeyss')
        print("inside SETNATKEY POST")
        print(os.path.dirname(__file__)+'/serviceAccountKey.json')

        try:
            print('inside try')
            default_app=firebase_admin.get_app('natfbloginsingupapp')
            print('about inside try')
        except ValueError:
            print('inside value error')
            cred = credentials.Certificate(os.path.dirname(__file__)+'/serviceAccountKey.json')
            default_app = firebase_admin.initialize_app(credential=cred,name='natfbloginsingupapp')
        else:
            pass
        
        print("inside natkeys")
        payload = request.stream.read().decode('utf8')
        payload1=json.loads(payload)
        print(payload1)
        id_token1=payload1['natkey']
        id_token2=id_token1['stsTokenManager']
        id_token=id_token2['accessToken']
        print(type(payload1))
        print(id_token)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        try:
            decoded_token = auth.verify_id_token(id_token,app=default_app)
        except ValueError:
            errorresp= {'natstatus':'error','statusdetails':'Not a valid user credentials'}
            resps = make_response(jsonify(errorresp), 400)
            print(resps)
            return(resps)
        else:
            uid = decoded_token['uid']
            exp = decoded_token['exp']
            iat = decoded_token['iat']
            email = decoded_token['email']
            print(uid)
            print(decoded_token)
        
        #This is to be moved to a configurable place
        #conn_string = "host='localhost' dbname='postgres' user='postgres' password='password123'"
        #This is to be moved to a configurable place
        #con=psycopg2.connect(conn_string)
        #cur = con.cursor()
        con,cur=db.mydbopncon()

        #need to think on a way to get entity id for this

        command = cur.mogrify("SELECT lguserid,lgusername,lgusertype,lgentityid,lguserstatus,lguserlastlogin FROM webapp.userlogin WHERE lguserid = %s AND lguserstatus NOT IN ('S','I','B');",(uid,) )
        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(cur)
        print(dbqerr)
        print(type(dbqerr))
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="loginuser Fetch failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        else:
            pass
        
        records=[]
        for record in cur:  
            print('inside for')
            print(record)             
            records.append(record)

        print(len(records))

        #if len(records) == 0:
        if (cur.rowcount) == 0:
            errorresp= {'natstatus':'error','statusdetails':'User not registered/activated/blocked'}
            resps = make_response(jsonify(errorresp), 400)
            print(resps)    
            return(resps)
        else:
            lguserid,lgusername,lgusertype,lgentityid,lguserstatus,lguserlastlogin = records[0]
  
        print(lguserid)
        print(lgusername)
        print(lgusertype)   
        print(lgentityid)
        print(lguserstatus)
        if lguserlastlogin is not None:
            print(lguserlastlogin.strftime('%Y-%m-%d %H:%M:%S'))
            lguserlastlogin=lguserlastlogin.strftime('%Y-%m-%d %H:%M:%S')
        else:
            lguserlastlogin=''

        #Update login table with the login time etc START

        command = cur.mogrify("UPDATE webapp.userlogin SET lguserlastlogin = (SELECT (CASE WHEN (lgusercurrentlogin IS NULL OR lgusercurrentlogin < '01-01-1980') THEN CURRENT_TIMESTAMP ELSE lgusercurrentlogin END) AS lgusercurrentlogin FROM webapp.userlogin WHERE lguserid = %s AND lgentityid = %s), lgusercurrentlogin = CURRENT_TIMESTAMP WHERE lguserid = %s AND lgentityid = %s;",(uid,lgentityid,uid,lgentityid,))
        #command1 = cur.mogrify("select json_agg(c) from (SELECT nfuuid,nfumessage,nfumsgtype FROM notifiuser WHERE nfuuserid = %s AND nfuentityid = %s AND nfuscreenid='dashboard' AND nfustatus = 'C' and nfulazyldid = %s) as c;",(userid,entityid,lazyloadid) )
        print('after lazid update')   
        print(command)            
        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="pf Fetch failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        #con.commit()                  
        print(cur)
        print('consider insert or update is successful')

        #Update login table with the login time etc END

        '''
        #code to prove all update statemnts are in a transaction untill commit is explicitly issued
        #test code start
        command = cur.mogrify("UPDATE webapp.userlogin SET LGSINUPUSERNAME = 'TESTUSER' WHERE lguserid = 'BfulXOzj3ibSPSBDVgzMEAF1gax1' AND lgentityid = 'IN';")
        cur, dbqerr = db.mydbfunc(con,cur,command)
        
        print('################commit####################')
        #con.rollback()
        print('################commit####################')
        con.commit()
        print('################commit####################')
        #test code end
        '''
        natseckey='secret'

        command = cur.mogrify("select secretcode,seccdid from webapp.secrettkn;" )
        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(cur)
        print(dbqerr)
        print(type(dbqerr))
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="loginuser Fetch failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        else:
            pass
        
        records=[]
        for record in cur:  
            print('inside for')
            print(record)             
            records.append(record)

        print(len(records))

        if len(records) == 0:
            errorresp= {'natstatus':'error','statusdetails':'DB error (token creation failure)'}
            resps = make_response(jsonify(errorresp), 400)
            print(resps)
            return(resps)
        else:
            secretcode,seccdid = records[0]


        #Call JWT to generate JWT START
        natjwt =  jwt.encode({'uid': lguserid,'entityid':lgentityid,'username':lgusername,'lastlogin':lguserlastlogin,'userstatus':lguserstatus,'exp': exp,'iat': iat, 'usertype':lgusertype,'skd':seccdid}, secretcode, algorithm='HS256')          
        print("printing nat jwt")
        print(natjwt)
        #Call JWT to generate JWT END
        db.mydbcloseall(con,cur)
        return (json.dumps({"natjwt" :natjwt.decode("utf-8")}))
    
@app.route('/signup',methods=['GET','POST','OPTIONS'])
def signupf():
#This is called by setjws service
    if request.method=='OPTIONS':
        print("inside signup options")
        return 'inside signup options'

    elif request.method=='POST':
        print("inside signup POST")
        
        #This is hardcoded only now.  Incase of lauch in different entity this is to be get from front end.
        lgentityid = 'IN'

        try:
            print('inside try')
            default_app=firebase_admin.get_app('natfbloginsingupapp')
            print('about inside try')
        except ValueError:
            print('inside value error')
            cred = credentials.Certificate(os.path.dirname(__file__)+'/serviceAccountKey.json')
            default_app = firebase_admin.initialize_app(credential=cred,name='natfbloginsingupapp')
        else:
            pass     
        
        
        print("inside signup")
        payload = request.stream.read().decode('utf8')
        payload1=json.loads(payload)
        print(payload1)
        id_token1=payload1['natkey']
        id_token2=id_token1['stsTokenManager']
        id_token=id_token2['accessToken']
        print(type(payload1))
        print(id_token)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        try:
            decoded_token = auth.verify_id_token(id_token,app=default_app)
        except ValueError:
            errorresp= {'natstatus':'error','statusdetails':'Invalid token'}
            resps = make_response(jsonify(errorresp), 400)
            print(resps)
            return(resps)
        else:
            uid = decoded_token['uid']
            exp = decoded_token['exp']
            iat = decoded_token['iat']
            email = decoded_token['email']
            print(uid)
            print(decoded_token)
            print('decoding successful')

        signupdata = payload1['signupvalue']
        print(signupdata)
        lguserid = uid
        lgsinupusername = signupdata['name']
        lgsinupadhaar= signupdata['adhaar']
        lgsinuppan= signupdata['pan']
        lgsinupmobile= signupdata['mobile']
        lgsinupemail=email
        lgusertype='W'
        lguserstatus = 'S'
        nfmid=datetime.now().strftime('%Y%m%d%H%M%S')
        print('nfmid :',nfmid)
        updtsignup = True
        
        
        #This is to be moved to a configurable place
        #conn_string = "host='localhost' dbname='postgres' user='postgres' password='password123'"
        #This is to be moved to a configurable place
        #con=psycopg2.connect(conn_string)
        #cur = con.cursor()
        con,cur=db.mydbopncon()

        #login method check
        command = cur.mogrify("select lguserid from webapp.userlogin where lguserid = %s ;",(lguserid,) )
        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="userid check fetch failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        else:
            pass
        
        records=[]
        for record in cur:  
            records.append(record)
        if len(records) == 0:
            #lguserid = records[0]
            pass
        else:
            updtsignup = False
            errorresp= {'natstatus':'error','statusdetails':'User signed up with the same method'}
            resps = make_response(jsonify(errorresp), 400)
            return(resps)
        print('------------------%%%%%--------------')

        #Adhaar check
        command = cur.mogrify("select lgsinupadhaar from webapp.userlogin where lgsinupadhaar = %s ;",(lgsinupadhaar,) )
        print(command)

        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="userid check fetch failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        else:
            pass

        records=[]
        for record in cur:  
            records.append(record)
        if len(records) == 0:
            #lgsinupadhaar = records[0]
            pass
        else:
            updtsignup = False
            errorresp= {'natstatus':'error','statusdetails':'Adhaar Already Signed up'}
            resps = make_response(jsonify(errorresp), 400)
            return(resps)
        
        print('------------------%%%%%--------------')

        #PAN check
        command = cur.mogrify("select lgsinuppan from webapp.userlogin where lgsinuppan = %s ;",(lgsinuppan,) )
        print(command)

        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="panid check fetch failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        else:
            pass
        
        records=[]
        for record in cur:  
            records.append(record)
        if len(records) == 0:
            #lgsinuppan = records[0]
            pass
        else:
            updtsignup = False
            errorresp= {'natstatus':'error','statusdetails':'PAN Already Signed up'}
            resps = make_response(jsonify(errorresp), 400)
            return(resps)

        print('------------------#####--------------')
        command = cur.mogrify("BEGIN;")
        cur, dbqerr = db.mydbfunc(con,cur,command)
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="DB query failed, BEGIN failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)

        if updtsignup == True:
            #READY to Signup

            command = cur.mogrify("INSERT INTO webapp.userlogin (lguserid, lgsinupusername,lgsinupadhaar,lgsinuppan,lgsinupmobile,lgsinupemail,lgusertype,lguserstatus,lguserstatusupdt,lgoctime,lglmtime,lgentityid) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,%s);",(lguserid, lgsinupusername,lgsinupadhaar,lgsinuppan,lgsinupmobile,lgsinupemail,lgusertype,lguserstatus,lgentityid,))
            cur, dbqerr = db.mydbfunc(con,cur,command)
            print(dbqerr['natstatus'])
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="SIGNUP update failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            #con.commit()                  
            print(cur)
            print('consider insert or update is successful')

            responsemsg = "User signup successful. Activation email will be sent to "+ email
            #print(responsemsg)

            #INSERT to uccclientmaster & fatcaupload START

            #-----INSERT uccclientmaster Insert START
            command = cur.mogrify("INSERT INTO webapp.uccclientmaster (ucclguserid,CLIENTCODE,CLIENTPAN,CM_MOBILE,CLIENTEMAIL,uccoctime,ucclmtime,uccentityid) VALUES (%s,concat('A',(right((lpad(cast(nextval('webapp.ucc_clientcode_seq') as text),10,'0')),9))),%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,%s);",(lguserid,lgsinuppan,lgsinupmobile,lgsinupemail,lgentityid,))
            cur, dbqerr = db.mydbfunc(con,cur,command)
            print(dbqerr['natstatus'])
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="UCCCLIENTMASTER INSERT failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            #con.commit()                  
            print(cur)
            print('consider insert or update is successful')
            #-----INSERT uccclientmaster Insert END

            #-----INSERT fatcamaster Insert START
            command = cur.mogrify("INSERT INTO webapp.fatcamaster (fatcalguserid,PAN_RP,fatcaoctime,fatcalmtime,fatcaentityid) VALUES(%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,%s);",(lguserid,lgsinuppan,lgentityid,))
            cur, dbqerr = db.mydbfunc(con,cur,command)
            print(dbqerr['natstatus'])
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="FATCAUPLOAD INSERT failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            #con.commit()                  
            print(cur)
            print('consider insert or update is successful')
            #-----INSERT fatcamaster Insert END

            #INSERT to uccclientmaster & fatcamaster END

            print('Client sign up success in All insert updates')
        print('sign up completion response',responsemsg,'will be sent')
        con.commit()
        
        responsemsg = checkpanstatus(lgsinuppan,con,cur,lguserid,lgentityid)
        
        db.mydbcloseall(con,cur)

        return (json.dumps({'natstatus':'success','statusdetails':responsemsg}))

@app.route('/updatekyc',methods=['GET','OPTIONS'])
def updatekyc():
#This is called by fund data fetch service
    if request.method=='OPTIONS':
        print("inside pforderdatafetch options")
        return make_response(jsonify('inside FUNDDATAFETCH options'), 200)  

    elif request.method=='GET':
        print("inside pforderdatafetch GET")
        print((request))        
        print(request.headers)
        userid,entityid=jwtnoverify.validatetoken(request)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print(userid,entityid)
        print('after')
        
        con,cur=db.mydbopncon()
        
        print(con)
        print(cur)

        command = cur.mogrify("SELECT lgsinuppan FROM webapp.userlogin WHERE lguserid = %s AND lgentityid = %s;",(userid,entityid,) )
        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="pf Fetch failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)


        #Model to follow in all fetch
        records=[]
        for record in cur:  
            records.append(record[0])    

        responsemsg = checkpanstatus(records[0],con,cur,userid,entityid)

    return (json.dumps({'natstatus':'success','statusdetails':responsemsg})) 


def checkpanstatus(lgsinuppan,con,cur,lguserid,lgentityid):
    kycstatus = ["KYC Not Registered", "KYC Registered-New KYC"]
    responsemsgpan = panv.pancard_verify(lgsinuppan)
    panname = responsemsgpan.get('pan_name')
    kycstatusresp = responsemsgpan.get('kyc_status')
    nfmid=datetime.now().strftime('%Y%m%d%H%M%S')

    
    if kycstatusresp == "KYC Registered-New KYC":

        command = cur.mogrify("BEGIN;")
        cur, dbqerr = db.mydbfunc(con,cur,command)
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="DB query failed, BEGIN failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)


        #----- UPDATE user status START
        command = cur.mogrify("UPDATE webapp.userlogin SET lgusername = %s , lguserstatus='R' WHERE lguserid=%s AND lgentityid = %s;",(panname,lguserid,lgentityid,))
        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="LGUSERNAME Update failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        #con.commit()                  
        print(cur)
        print('consider insert or update is successful')
        #-----INSERT fatcamaster Insert END

        #----- UPDATE user status START
        command = cur.mogrify("UPDATE webapp.uccclientmaster SET CLIENTAPPNAME1 = %s WHERE ucclguserid=%s AND uccentityid = %s;",(panname,lguserid,lgentityid,))
        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="UCCLIENTMASTER User name update failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        #con.commit()                  
        print(cur)
        print('consider insert or update is successful')
        #-----INSERT fatcamaster Insert END

        #----- UPDATE user status START
        command = cur.mogrify("UPDATE webapp.fatcamaster SET inv_name = %s WHERE fatcalguserid=%s AND fatcaentityid = %s;",(panname,lguserid,lgentityid,))
        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="UCCLIENTMASTER User name update failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        #con.commit()                  
        print(cur)
        print('consider insert or update is successful')
        #-----INSERT fatcamaster Insert END


        #INSERT NOTIFICATION ENTRY FOR PENDING USER REGISTRAION COMPLETION START
        
        command = cur.mogrify("INSERT INTO webapp.notifimaster (nfmid,nfname,nfmuserid,nfmscreenid,nfmessage,nfmsgtype,nfmprocessscope,nfmnxtact,nfmnxtactmsg,nfmnxtactnavtyp,nfmnxtactnavdest,nfmstartdt,nfmoctime,nfmlmtime,nfmentityid) VALUES (%s,'pendingkyc',%s,'dashboard','<div fxLayout=#column# fxLayoutWrap><div><p> Welcome. You need complete your registration before start buying the funds. Please complete user registration </p><p>Go to Setting > Registration </div><div>','notifaction','P','Y','','NONE','NONE',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,%s) ON CONFLICT ON CONSTRAINT notimastuniq DO NOTHING;",(nfmid,lguserid,lgentityid,))
        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="SIGNUP notifimaster update failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        #con.commit()                  
        print(cur)
        print('consider insert or update is successful')

        #INSERT NOTIFICATION ENTRY FOR PENDING USER REGISTRAION COMPLETION END

    else:
        #----- UPDATE user status START
        command = cur.mogrify("UPDATE webapp.userlogin SET lguserstatus='K' WHERE lguserid=%s AND lgentityid = %s;",(lguserid,lgentityid,))
        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="LGUSERNAME Update failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        #con.commit()                  
        print(cur)
        print('consider insert or update is successful')
        #-----INSERT fatcamaster Insert END

        #INSERT NOTIFICATION ENTRY FOR PENDING USER REGISTRAION COMPLETION START
        command = cur.mogrify("INSERT INTO webapp.notifimaster (nfmid,nfname,nfmuserid,nfmscreenid,nfmessage,nfmsgtype,nfmprocessscope,nfmnxtact,nfmnxtactmsg,nfmnxtactnavtyp,nfmnxtactnavdest,nfmstartdt,nfmoctime,nfmlmtime,nfmentityid) VALUES (%s,'pendingregistration',%s,'dashboard','<div fxLayout=#column# fxLayoutWrap><div><p> Welcome. Looks like you have not done KYC. Please complete your KYC </p><p>Go to FAQ to know more </div><br><div><button mat-button color = #primary#>Update KYC status</button></div><div>','notifaction','P','Y','','NONE','NONE',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,%s);",(nfmid,lguserid,lgentityid,))
        cur, dbqerr = db.mydbfunc(con,cur,command)
        print(dbqerr['natstatus'])
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="SIGNUP notifimaster update failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        #con.commit()                  
        print(cur)
        print('consider insert or update is successful')

        #INSERT NOTIFICATION ENTRY FOR PENDING USER REGISTRAION COMPLETION END
    con.commit()    
    responsemsg = "Signup successful. Please login with registered user id"
    return responsemsg

