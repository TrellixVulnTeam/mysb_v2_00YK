from pf import app
from flask import redirect, request,make_response, jsonify

from datetime import datetime, timedelta
import pf.notificationprocessing as np
from pf import dbfunc as db

import psycopg2
import jwt
import requests
import json
import time

      
@app.route('/notification',methods=['GET','POST','OPTIONS'])
def mainnotification():
#This is called by notification service
    if request.method=='OPTIONS':
        print("inside notification options")
        return make_response(jsonify('inside notification options'), 200)  

    elif request.method=='GET':
        print("inside notification GET")
        print((request))
        lazyloadid=request.args.get('lazldid')
        print('value of lazyload',lazyloadid)
        module=request.args.get('module')
        print('value of module',module)
        userid,entityid=validatetoken(request)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        

        #This is to be moved to a configurable place
        #conn_string = "host='localhost' dbname='postgres' user='postgres' password='password123'"
        #This is to be moved to a configurable place
        #con=psycopg2.connect(conn_string)
        #cur = con.cursor()

        con,cur=db.mydbopncon()
        print(lazyloadid)
    

        if module == 'signin':

            print('inside sigin')
            #move this code inside notificationprocessing
            '''
            r = requests.post("http://0.0.0.0:8001/notiprocess", data=json.dumps({'module':'signin','lazyloadid': lazyloadid,'userid':userid,'entityid':entityid}))
            print(r.text)
            #isnotiusrup2dt=cknotiusrup2dt(userid,entityid,con,cur)
            #start the processing multiprocess      
            '''      
            return 'ok'

        elif module == 'dashboard':
            print('inside dashboard')
            if lazyloadid =='':
                lazyloadid = datetime.now().strftime('%Y%m%d%H%M%S')
                print(lazyloadid)

            '''
            lambda_client = boto3.client('lambda', region_name='my-region')
            # trigger the next lambda function
            res = client.invoke(
                FunctionName='notiprocess',
                InvocationType='RequestResponse',
                Payload=json.dumps({'module':'dashboard',lazyloadid': lazyloadid,'userid':userid,'entityid',entityid})
            '''
            rj = {'module':'dashboard','lazldid': lazyloadid,'userid':userid,'entityid':entityid}
            #r = requests.post('http://127.0.0.1:8000/notiprocess',json = rj)
            #r=requests.get('http://www.mocky.io/v2/5a5797022e0000b03f120260')
            print('#################')
            #print(r.json())
            print('#################')
            
            # to be deleted this is for testing only
            isnotiusrup2dt = np.cknotiusrup2dt('dashboard',userid,entityid,con,cur)
            command = cur.mogrify("UPDATE webapp.notifiuser SET nfulazyldid = %s,  nfulazyldidstatus = 'P', nfustatus = 'C';",(lazyloadid,))
            print(command)
            cur, dbqerr = db.mydbfunc(con,cur,command)
            con.commit()
            print('commiting notifiuser')
            #time.sleep(10)
            # to be deleted this is for testing only
        elif lazyloadid != 'dashboard' or lazyloadid != 'signin':
            pass

        #command=command1
        command = cur.mogrify("select json_agg(c) from (SELECT nfumid,nfumessage,nfumsgtype FROM webapp.notifiuser WHERE nfuuserid = %s AND nfuentityid = %s AND nfuscreenid='dashboard' AND nfustatus = 'C' and nfulazyldidstatus != 'S' and nfulazyldid = %s) as c;",(userid,entityid,lazyloadid) )
        #command = cur.mogrify(";",(userid,entityid,lazyloadid) )
        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
        rowcount = cur.rowcount
        print(rowcount)
        if rowcount != 0:
            records=[]
            for record in cur:  
                print('inside for')
                print(record) 
                print(record[0]) 
                print(json.dumps(record[0]))            
                records.append(record[0])     
            #this is to be returned start
            print(records[0])
            print(json.dumps(records[0]))
            notifyrecrods=records[0]
            #this is to be returned end
            print('going into ')
            if record[0]:
                for key in records[0]:
                    value=key['nfumid']
                    print(type(value))
                    qryst = value + """','"""
                qryst=qryst[:-3]
            #qryst="""'"""+qryst+"""'"""
                print(qryst)
                print(type(qryst))
                hvrecordstosend = True     
            elif record[0]==0:
                hvrecordstosend = False                
            else:
                hvrecordstosend = False
                #lazyloadid=chkifalldone(con,cur,command,lazyloadid,userid,entityid)

       
        print(userid)
        print(lazyloadid)
        print(hvrecordstosend)
        if hvrecordstosend == True:
            command = cur.mogrify("UPDATE webapp.notifiuser SET nfulazyldidstatus = 'S' WHERE nfuuserid = %s AND nfuentityid = %s AND nfumid in (%s) and nfulazyldid = %s",(userid,entityid,qryst,lazyloadid,) )
            print(command)
            print('after final lazid update')               
            cur, dbqerr = db.mydbfunc(con,cur,command)
            print(dbqerr['natstatus'])
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="pf Fetch failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            con.commit()                  
            print(cur)
            print('consider insert or update is successful')
        else:
            pass       
        
        lazyloadid=chkifalldone(con,cur,command,lazyloadid,userid,entityid)
        print(notifyrecrods,'for lazyldid',lazyloadid)
    return json.dumps({'data':notifyrecrods,'lazyloadid':lazyloadid})


def chkifalldone(con,cur,command,lazyloadid,userid,entityid):                
    command = cur.mogrify("select count(*) FROM webapp.notifiuser WHERE nfuuserid = %s AND nfuentityid = %s AND nfulazyldidstatus != 'S' and nfulazyldid = %s;",(userid,entityid,lazyloadid,) )
    print('--------------------------------')
    print(command)
    cur, dbqerr = db.mydbfunc(con,cur,command)
    record=cur.fetchall()                        
    print(record)
    print('--------------------------------')
    if record:          
        return  lazyloadid
    else:
        return ''


'''
def notiprocess(data):
    print(data)


def mydbfunc(con,cur,command):
    try:
        cur.execute(command)        
        myerror={'natstatus':'success','statusdetails':''}
    except psycopg2.Error as e:
        print(e)
        myerror= {'natstatus':'error','statusdetails':''}
    except psycopg2.Warning as e:
        print(e)
        myerror={'natstatus':'warning','statusdetails':''}
        #myerror = {'natstatus':'warning','statusdetails':e}
    finally:
        if myerror['natstatus'] != "success":    
            con.rollback()
            cur.close()
            con.close()
            
    return cur,myerror
'''

def validatetoken(request):
    
    if 'Authorization' in request.headers:

        natjwtfrhead=request.headers.get('Authorization')
        if natjwtfrhead.startswith("Bearer "):
            natjwtfrheadf =  natjwtfrhead[7:]
        natjwtdecoded = jwt.decode(natjwtfrheadf, verify=False)        
        userid=natjwtdecoded['uid']
        entityid='IN'
        dbqerr={}
        #entityid=natjwtdecoded['entityid']
        if  (not userid) or (userid ==""):
            dbqerr['natstatus'] = "error"
            dbqerr['statusdetails']="No user id in request"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        return userid,entityid