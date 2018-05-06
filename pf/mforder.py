from pf import app
from pf import dbfunc as db
from pf import jwtdecodenoverify as jwtnoverify
#from order import dbfunc as db
#from order import jwtdecodenoverify as jwtnoverify


#from order import app
from flask import request, make_response, jsonify, Response, redirect
from datetime import datetime
from order import dbfunc as db
from order import jwtdecodenoverify as jwtnoverify
from dateutil import tz
from datetime import datetime
from datetime import date
from multiprocessing import Process
from multiprocessing import Pool
from pf import mforderapi
import requests

import psycopg2
import json
import jwt
import time

@app.route('/mforderdatafetch',methods=['GET','OPTIONS'])
def mforderdatafetch():
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
        
        #cur.execute("select row_to_json(art) from (select a.*, (select json_agg(b) from (select * from pfstklist where pfportfolioid = a.pfportfolioid ) as b) as pfstklist, (select json_agg(c) from (select * from pfmflist where pfportfolioid = a.pfportfolioid ) as c) as pfmflist from pfmaindetail as a where pfuserid =%s ) art",(userid,))
        #command = cur.mogrify("select row_to_json(art) from (select a.*,(select json_agg(b) from (select * from webapp.pfstklist where pfportfolioid = a.pfportfolioid ) as b) as pfstklist, (select json_agg(c) from (select c.*,(select json_agg(d) from (select * from webapp.pfmforlist where orormflistid = c.ormflistid AND ormffndstatus='INCART' AND entityid=%s) as d) as ormffundorderlists from webapp.pfmflist c where orportfolioid = a.pfportfolioid ) as c) as pfmflist from webapp.pfmaindetail as a where pfuserid =%s AND entityid=%s) art",(entityid,userid,entityid,))
        command = cur.mogrify(
            """
        	WITH portport as (select ororportfolioid,orormflistid,orormfpflistid from webapp.pfmforlist where ormffndstatus = 'INCART' AND ororpfuserid = %s AND entityid = %s) 
            select row_to_json(art) from (
            select a.*,
            (select json_agg(b) from (select * from webapp.pfstklist where pfportfolioid = a.pfportfolioid ) as b) as pfstklist, 
            (select json_agg(c) from (select c.*,(select json_agg(d) from (select * from webapp.pfmforlist where orormflistid in (SELECT distinct orormflistid FROM PORTPORT) AND ororportfolioid =a.pfportfolioid AND orormflistid=c.ormflistid AND ormffndstatus = 'INCART' AND entityid = %s ORDER BY ormffundordelstrtyp) as d) as ormffundorderlists 
            from webapp.pfmflist c where ormflistid in (SELECT distinct orormflistid FROM portport) AND  entityid = %s AND orportfolioid =a .pfportfolioid ) as c) as pfmflist 
	        from webapp.pfmaindetail as a where pfuserid = %s AND entityid = %s AND pfportfolioid IN (SELECT distinct ororportfolioid FROM portport) ORDER BY pfportfolioid  ) art
            """,(userid,entityid,entityid,entityid,userid,entityid,))

        cur, dbqerr = db.mydbfunc(con,cur,command)
        print("#########################################3")
        print(command)
        print("#########################################3")
        print(cur)
        print(dbqerr)
        print(type(dbqerr))
        print(dbqerr['natstatus'])
        
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="pf Fetch failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)


        #Model to follow in all fetch
        records=[]
        for record in cur:  
            records.append(record[0])           



        print("portfolio details returned for user: "+userid)
        
        
        resp = json.dumps(records)
    
    return resp



@app.route('/mfordersave',methods=['GET','POST','OPTIONS'])
#example for model code http://www.postgresqltutorial.com/postgresql-python/transaction/
def mfordersave():
    
    if request.method=='OPTIONS':
        print ("inside mfordersave options")
        return jsonify({'body':'success'})

    elif request.method=='POST':   
        print ("inside mfordersave post")

        print(request.headers)
        payload= request.get_json()
        #payload = request.stream.read().decode('utf8')    
        
        pfdatas = payload
        print(pfdatas)
        
        userid,entityid=jwtnoverify.validatetoken(request)
        con,cur=db.mydbopncon()

        command = cur.mogrify("BEGIN;")
        cur, dbqerr = db.mydbfunc(con,cur,command)
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="DB query failed, BEGIN failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)

        savetimestamp = datetime.now()
        pfsavedate=savetimestamp.strftime('%Y%m%d') 
        pfsavetimestamp=savetimestamp.strftime('%Y/%m/%d %H:%M:%S')


        for pfdata in pfdatas:
            pfmflsdatalist=[]
            pfmforlsdatalist=[]
            print("pfdata before removing")
            print(pfdata)
            savetype = ""
            if 'pfportfolioid' in pfdata:
                if pfdata.get('pfportfolioid') == "NEW":
                    savetype = "New"
                else:
                    savetype = "Old"
            else:
                #if 'pfportfolioid' itself not in the data it is error we shouuld exit
                print('pfportfolioid is not in the messages')
                return jsonify({'natstatus':'error','statusdetails':'Data error (Portfolio id missing)'})

            if 'pfstklist' in pfdata:
                pfstlsdata = pfdata.pop("pfstklist")            
                print("pfstlsdata")
            else:
                pfstlsdata=None
                print("key pfstklist not in the submitted record")
                #return jsonify({'natstatus':'error','statusdetails':'Data error (stocklist missing)'})
            
            if 'pfmflist' in pfdata:
                pfmflsdata = pfdata.pop("pfmflist")
                print("pfmflist")
                print(pfmflsdata)
            else:
                pfmflsdata=None
                print("key pfmflist not in the submitted record")
                #return jsonify({'natstatus':'error','statusdetails':'Data error (mflist missing)'})

            if'pfscreen' in pfdata:
                screenid= pfdata.get('pfscreen')
                if screenid == "pfs":
                    filterstr="NEW"
                elif screenid == "ord":
                    filterstr="INCART"
            else:
                screenid=None
                print("key screenid not in the submitted record")       


            print("after removing")
            print("pfdata")
            print(pfdata)
            
            print("pfsavetimestamp1")
            print("pfsavetimestamp1")
            #useridstr=pfdata.get('pfuserid')
            useridstr=userid
            pfdata['pfuserid']=userid

            if savetype == "New": 
                #No New portfolio should come here
                pass
            elif savetype == "Old" :
                print('inside old')
                pfdata['pflmtime']= pfsavetimestamp
                pfdata.get('pfuserid')            

                #If request is from pfscreen then we update pf details, if it is from order screen skip this.
                
                ###PF stock details update START###
                    #NO STOCK DETAILS FOR THIS FUNCTION TO HANDLE
                ###PF stock details update END###

                ###PF MF details update START###

                if pfmflsdata!=None:
                    for d in pfmflsdata:  
                        print("pfmflsdata inside for")
                        print(d)
                        d['ormfoctime']= pfsavetimestamp
                        d['ormflmtime']= pfsavetimestamp

                        if(d['ormflistid']==""):
                            #New fund getting added to the PF
                            command = cur.mogrify("SELECT MAX(ormfseqnum) FROM webapp.pfmflist where orportfolioid = %s and entityid =%s;",(pfdata.get('pfportfolioid'),entityid,))
                            print(command)
                            cur, dbqerr = db.mydbfunc(con,cur,command)
                                                
                            if cur.closed == True:
                                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                                    dbqerr['statusdetails']="Fund MAX sequence failed"
                                resp = make_response(jsonify(dbqerr), 400)
                                return(resp)

                            #Model to follow in all fetch
                            records=[]
                            for record in cur:  
                                records.append(record[0])
                            print("iam printing records to see")
                            print(records)
                            
                            if(records[0] == None):
                                pfmflsseqnum=1
                            else:
                                if(type(records[0])=="Decimal"):
                                    pfmflsseqnum = int(Decimal(records[0]))+1                                
                                else:
                                    pfmflsseqnum=records[0]+1

                            d['ormflistid']='mf'+pfdata.get('pfportfolioid')+str(pfmflsseqnum)
                            d['orportfolioid']=pfdata.get('pfportfolioid')
                            d['entityid']=entityid
                            d['ormfseqnum'] = str(pfmflsseqnum)
                            d['orpfuserid']=pfdata.get('pfuserid')
                            pfmflsdatalist.append(d['ormflistid'])
                            

                            if 'ormffundorderlists' in d:
                                pfmflsordata = d.pop("ormffundorderlists")
                                print("ormffundorderlists old")
                                print(pfmflsordata)
                            else:
                                pfmflsordata=None
                                print("key ormffundorderlists not in the submitted record")

                            pfmflsdatajsondict = json.dumps(d)
                            command = cur.mogrify("INSERT INTO webapp.pfmflist select * from json_populate_record(NULL::webapp.pfmflist,%s) where entityid = %s;",(str(pfmflsdatajsondict),entityid,))
                            print(command)                
                            cur, dbqerr = db.mydbfunc(con,cur,command)
                            if cur.closed == True:
                                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                                    dbqerr['statusdetails']="mflist insert Failed"
                                resp = make_response(jsonify(dbqerr), 400)
                                return(resp)

                            pfmforlsseqnum=1
                            if pfmflsordata != None:
                                for e in pfmflsordata: 
                                    print("PRINTING e")
                                    print(e)                                           
                                    e['ormfoctime']= pfsavetimestamp
                                    e['ormflmtime']= pfsavetimestamp
                                    e['entityid']=entityid
                                    #e['orormfpflistid']= "or"+d.get('ormflistid')+str(pfmforlsseqnum)
                                    e['ororportfolioid']=d.get('orportfolioid')
                                    e['orpfportfolioname']=pfdata.get('pfportfolioname')
                                    e['ororpfuserid']=d.get('orpfuserid')
                                    e['orormffundname']=d.get('ormffundname')
                                    e['orormffndcode']=d.get('ormffndcode')
                                    e['orormflistid']= d.get('ormflistid') 
                                    
                                    if(e.get('ormffundordelsstdt')==0):
                                        if (e['ormffundordelstrtyp']=='One Time'):
                                            print("inside if")
                                        else:
                                            dbqerr={}
                                            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                                                dbqerr['statusdetails']="SIP START DATE is Mandatory"
                                            resp = make_response(jsonify(dbqerr), 400)
                                            return(resp)
                                        
                                    
                                    #For new SIP or onetime record for the fund
                                    if(e['orormfpflistid'] ==""):
                                        e['orormfpflistid']= "or"+d.get('ormflistid')+str(pfmforlsseqnum)                                                                 
                                        e['orormfseqnum'] = pfmforlsseqnum
                                        pfmforlsdatalist.append(e['orormfpflistid'])
                                        pfmforlsseqnum = pfmforlsseqnum+1
                                        pfmflsordatajsondict = json.dumps(e)

                                        command = cur.mogrify("INSERT INTO webapp.pfmforlist select * from json_populate_record(NULL::webapp.pfmforlist,%s) where entityid = %s;",(str(pfmflsordatajsondict),entityid,))
                                        print(command)
                                        cur, dbqerr = db.mydbfunc(con,cur,command)
                                        if cur.closed == True:
                                            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                                                dbqerr['statusdetails']="mflist details insert Failed"
                                            resp = make_response(jsonify(dbqerr), 400)
                                            return(resp)
                                    else:
                                        #For existing SIP or onetime record for the fund
                                        pass
                                        #'''
                                        #This condition doesn't come for new fund insert itself so commenting.
                                        #command = cur.mogrify("UPDATE webapp.pfmforlist select * from json_populate_record(NULL::webapp.pfmforlist,%s) where orormfpflistid = %s and entityid = %s",(str(pfmflsordatajsondict),e.get('orormfpflistid'),entityid,))
                                        
                                        #cur, dbqerr = db.mydbfunc(con,cur,command)
                                        #if cur.closed == True:
                                        #    if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                                        #        dbqerr['statusdetails']="mflist details insert Failed"
                                        #    resp = make_response(jsonify(dbqerr), 400)
                                        #    return(resp)
                                        #'''
                            else:
                                pass
                        else:
                            #fund is existing so we have to update
                            print("existing fund upate")
                            d['entityid']=entityid
                            d['orpfuserid']=pfdata.get('pfuserid')
                            pfmflsdatalist.append(d['ormflistid'])

                            if 'ormffundorderlists' in d:
                                pfmflsordata = d.pop("ormffundorderlists")
                                print("ormffundorderlists old")
                                print(pfmflsordata)
                            else:
                                pfmflsordata=None
                                print("key ormffundorderlists not in the submitted record")

                            pfmflsdatajsondict = json.dumps(d)
                            #command = cur.mogrify("UPDATE webapp.pfmflist select * from json_populate_record(NULL::webapp.pfmflist,%s) WHERE ormflistid =%s AND entityid = %s;",(str(pfmflsdatajsondict),d.get('ormflistid'),entityid,))
                            
                            #donot update if the fund is fixed : START
                            if(d['ormffndnameedit'] == 'fixed'):
                                command = cur.mogrify("""
                                            UPDATE webapp.pfmflist set(ormffundname,ormffndcode,ormffndnameedit,ormfdathold,ormflmtime) = 
                                            (select ormffundname,ormffndcode,ormffndnameedit,ormfdathold,ormflmtime from json_to_record (%s)
                                            AS (ormffundname varchar(100),ormffndcode varchar(100),ormffndnameedit varchar(100),ormfdathold text,ormflmtime timestamp))
                                            WHERE ormflistid =%s AND entityid = %s;
                                        """,(str(pfmflsdatajsondict),d.get('ormflistid'),entityid,))                       
                                print(command)                
                                cur, dbqerr = db.mydbfunc(con,cur,command)
                                if cur.closed == True:
                                    if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                                        dbqerr['statusdetails']="mflist insert Failed"
                                    resp = make_response(jsonify(dbqerr), 400)
                                    return(resp)
                            #donot update if the fund is fixed : END

                            #pfmforlsseqnum=1
                            if pfmflsordata != None:
                                for e in pfmflsordata: 
                                    print("PRINTING e")
                                    print(e)                                           
                                    e['ormfoctime']= pfsavetimestamp
                                    e['ormflmtime']= pfsavetimestamp
                                    #e['orormfpflistid']= "or"+d.get('ormflistid')+str(pfmforlsseqnum)
                                    e['orormffundname']=d.get('ormffundname')
                                    e['orormffndcode']=d.get('ormffndcode')
                                    e['entityid']=entityid

                                    #For new SIP or onetime record for the fund
                                    if(e['orormfpflistid'] ==""):                                    
                                        command = cur.mogrify("SELECT MAX(orormfseqnum) FROM webapp.pfmforlist where orormflistid = %s and entityid =%s;",(d.get('ormflistid'),entityid,))
                                        print(command)
                                        cur, dbqerr = db.mydbfunc(con,cur,command)
                                                            
                                        if cur.closed == True:
                                            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                                                dbqerr['statusdetails']="Fund MAX sequence failed"
                                            resp = make_response(jsonify(dbqerr), 400)
                                            return(resp)

                                        #Model to follow in all fetch
                                        records=[]
                                        for record in cur:  
                                            records.append(record[0])
                                        print("iam printing records to see")
                                        print(type(records[0]))

                                        if(records[0] == None):
                                            pfmforlsseqnum=1
                                        else:
                                            if(type(records[0])=="Decimal"):
                                                pfmforlsseqnum = int(Decimal(records[0]))+1
                                                
                                            else:
                                                pfmforlsseqnum=records[0]+1
                                        print(pfmforlsseqnum)
                                        print(type(pfmforlsseqnum))
                                        e['orormfpflistid']= "or"+d.get('ormflistid')+str(pfmforlsseqnum)
                                        e['orormflistid']= d.get('ormflistid')
                                        e['orormfseqnum'] = str(pfmforlsseqnum)
                                        e['ororportfolioid']=d.get('orportfolioid')
                                        e['orpfportfolioname']=pfdata.get('pfportfolioname')
                                        e['ororpfuserid']=d.get('orpfuserid')
                                        pfmforlsdatalist.append(e['orormfpflistid'])
                                        
                                        pfmforlsseqnum = pfmforlsseqnum+1
                                        print(e)
                                        pfmflsordatajsondict = json.dumps(e)

                                        command = cur.mogrify("INSERT INTO webapp.pfmforlist select * from json_populate_record(NULL::webapp.pfmforlist,%s) where entityid = %s;",(str(pfmflsordatajsondict),entityid,))
                                        print(command)
                                        cur, dbqerr = db.mydbfunc(con,cur,command)
                                        if cur.closed == True:
                                            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                                                dbqerr['statusdetails']="mflist details insert Failed"
                                            resp = make_response(jsonify(dbqerr), 400)
                                            return(resp)
                                    else:
                                        #For existing SIP or onetime record for the fund

                                        pfmforlsdatalist.append(e['orormfpflistid'])
                                        pfmflsordatajsondict = json.dumps(e)                                    
                                        
                                        #Record which are only editable to be updated.
                                        if(e['ormffndstatus']=='INCART'):   
                                            command = cur.mogrify("""
                                                        UPDATE webapp.pfmforlist set(orormffundname,orormffndcode,ormffundordelsfreq,ormffundordelsstdt,ormffundordelsamt,ormfsipinstal,ormfsipendt,ormfsipdthold,ormfselctedsip,ormffndstatus,ormflmtime) = 
                                                        (select orormffundname,orormffndcode,ormffundordelsfreq,ormffundordelsstdt,ormffundordelsamt,ormfsipinstal,ormfsipendt,ormfsipdthold,ormfselctedsip,ormffndstatus,ormflmtime from json_to_record (%s)
                                                        AS (orormffundname varchar(100),orormffndcode varchar(100),ormffundordelsfreq varchar(20),ormffundordelsstdt varchar(11),ormffundordelsamt numeric(16,5),ormfsipinstal numeric(3),ormfsipendt date,ormfsipdthold text,ormfselctedsip text,ormffndstatus varchar(10),ormflmtime timestamp))
                                                        WHERE orormfpflistid = %s AND entityid = %s;
                                                    """,(str(pfmflsordatajsondict),e.get('orormfpflistid'),entityid,))


                                            cur, dbqerr = db.mydbfunc(con,cur,command)
                                            if cur.closed == True:
                                                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                                                    dbqerr['statusdetails']="mflist details insert Failed"
                                                resp = make_response(jsonify(dbqerr), 400)
                                                return(resp)
                                        else:
                                            pass
                            else:
                                pass
                    
                else:
                    print("done nothing as pfmflsdata is none") 

            #do the clean up of fund sip or oneitme records removed: START
            str2=tuple(pfmflsdatalist)
            print(pfmflsdatalist)
            print(str2)   

            #str3 = "','".join(pfmforlsdatalist)
            #str4 = "'" + str3 + "'"
            str4=tuple(pfmforlsdatalist)
            print(pfmforlsdatalist)
            print(str4)

            if pfmforlsdatalist:
                #Delete the records (SIP or One time records) that are deleted from a fund
                print("inside if")
                command = cur.mogrify("DELETE FROM webapp.pfmforlist where orormfpflistid NOT IN %s AND entityid =%s AND ororpfuserid = %s AND ororportfolioid = %s AND ormffndstatus = %s;",(str4,entityid,userid,pfdata.get('pfportfolioid'),filterstr,))
                print(command)
            else:
                #Delete all the records as all records (SIP or One time records) are deleted for a fund.  
                # But exclude ( this condition ormffndstatus = 'New') already executed order records.
                print("inside else")
                command = cur.mogrify("DELETE FROM webapp.pfmforlist where entityid =%s AND ororpfuserid = %s AND ororportfolioid = %s  AND ormffndstatus = %s;",(entityid,userid,pfdata.get('pfportfolioid'),filterstr,))
                print(command)            
            cur, dbqerr = db.mydbfunc(con,cur,command)
                                
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="Fund MAX sequence failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)

            #do the clean up of fund sip or oneitme records removed: END
        
            #do the clean up of funds removed: START
            if pfmflsdatalist:                
                command = cur.mogrify("DELETE FROM webapp.pfmflist where ormflistid NOT IN %s AND entityid =%s AND orpfuserid=%s AND orportfolioid= %s;",(str2,entityid,userid,pfdata.get('pfportfolioid'),))
                print(command)
            else:
                command = cur.mogrify("DELETE FROM webapp.pfmflist where entityid =%s AND orpfuserid=%s AND orportfolioid= %s;",(entityid,userid,pfdata.get('pfportfolioid'),))
                print(command)

            cur, dbqerr = db.mydbfunc(con,cur,command)
                                
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="Fund MAX sequence failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            
            #remove the fund where we don't have the any entry for order :START
            if pfmflsdatalist:
                command = cur.mogrify("DELETE FROM webapp.pfmflist where ormflistid IN (SELECT A.ormflistid FROM webapp.pfmflist A LEFT JOIN webapp.pfmforlist B ON A.ormflistid = B.orormflistid WHERE B.orormflistid IS NULL AND A.ormflistid IN %s AND A.entityid = %s) AND entityid =%s AND orpfuserid=%s AND orportfolioid= %s;",(str2,entityid,entityid,userid,pfdata.get('pfportfolioid'),))
                cur, dbqerr = db.mydbfunc(con,cur,command)

                if cur.closed == True:
                    if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                        dbqerr['statusdetails']="Fund MAX sequence failed"
                    resp = make_response(jsonify(dbqerr), 400)
                    return(resp)
            #remove the fund where we don't have the any entry for order :START
   
            #do the clean up of funds removed: END 
            ###PF MF details update END###

        print("All done and starting cleanups")

        # POST UPDATES FOR ORDER SCREEN : START
        '''
        if screenid == "ord":
            pass
        else:
            pass
        '''
        # POST UPDATES FOR ORDER SCREEN : END


        #POST UPDATES COMMON:START
        # Fund edit/delete allowed : START
        #If atleast one of the order is not new, we should not allow the fund to be removed and edited
        #in this case we mark ormffndnameedit as fixed    
        
        command = cur.mogrify("UPDATE webapp.pfmflist SET ormffndnameedit = 'fixed' WHERE ormflistid in (SELECT distinct orormflistid FROM webapp.pfmforlist WHERE UPPER(ormffndstatus) != 'NEW' and ororpfuserid = %s AND entityid = %s) AND 0 < (SELECT COUNT( distinct orormflistid) FROM webapp.pfmforlist WHERE UPPER(ormffndstatus) != 'NEW' and ororpfuserid = %s AND entityid = %s);",(userid,entityid,userid,entityid,))
        print(command)

        cur, dbqerr = db.mydbfunc(con,cur,command)
                            
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="Fund MAX sequence failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        # Fund edit/delete allowed : END

        #POST UPDATES COMMON:END

    con.commit()
    print('order details save successful')
    
    #clearuppostsave(pfmflsdatalist,pfmforlsdatalist,entityid,userid,pfdata)
    cur.close()
    con.close()
    return jsonify({'natstatus':'success','statusdetails':'Order details for ' + userid +' Saved/Updated'})


@app.route('/mfordervalidate',methods=['GET','POST','OPTIONS'])
#example for model code http://www.postgresqltutorial.com/postgresql-python/transaction/
def mfordervalidate():
    if request.method=='OPTIONS':
        print ("inside mfordervalidate options")
        return jsonify({'body':'success'})

    elif request.method=='POST':   
        print ("inside mfordervalidate post")

        print(request.headers)
        payload= request.get_json()
        #payload = request.stream.read().decode('utf8')    
        
        pfdatas = payload
        print(pfdatas)
        
        userid,entityid=jwtnoverify.validatetoken(request)
        con,cur=db.mydbopncon()

        command = cur.mogrify("BEGIN;")
        cur, dbqerr = db.mydbfunc(con,cur,command)
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="DB query failed, BEGIN failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)

        #select One Time records and enter in order processing table

        command = cur.mogrify("""
            INSERT INTO webapp.mforderdetails (mfor_prodcuttype,mfor_orormfpflistid,mfor_ororportfolioid,mfor_transactioncode,mfor_ordertype,mfor_buysell,mfor_orderstatus,
            mfor_transmode,mfor_dptxn,mfor_pfuserid,mfor_clientcode,mfor_schemecd,mfor_amount,mfor_foliono,mfor_kycstatus,mfor_euin,mfor_euinflag,mfor_dpc,mfor_ipadd,
            mfor_orderoctime,mfor_orderlmtime,mfor_entityid) 
            SELECT orormfprodtype,orormfpflistid,ororportfolioid,orormftrantype,ormffundordelstrtyp,orormfwhattran,'PNS',
            'P','P',ororpfuserid,B.clientcode,orormffndcode,ormffundordelsamt,D.fopfamcfolionumber,C.lguserkycstatus,'','N','N',C.lguseripaddress,
            CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,entityid from webapp.pfmforlist A 
            LEFT OUTER JOIN webapp.uccclientmaster B ON (A.ororpfuserid = B.ucclguserid AND A.entityid = B.uccentityid) 
            LEFT OUTER JOIN webapp.userlogin C ON (A.ororpfuserid = C.lguserid AND A.entityid = C.lgentityid) 
            LEFT OUTER JOIN webapp.mffoliodetails D ON (A.ororfndamcnatcode = D.foamcnatcode AND A.entityid = D.foentityid) 
            where ororpfuserid = %s AND entityid = %s AND ormffndstatus = 'INCART' AND ormffundordelstrtyp = 'One Time';
        """,(userid,entityid,))

        print(command)


        cur, dbqerr = db.mydbfunc(con,cur,command)
                            
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="Fund MAX sequence failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)


        command = cur.mogrify("""
            UPDATE webapp.pfmforlist SET ormffndstatus = 'SUBM' WHERE ororpfuserid = %s AND entityid = %s AND ormffndstatus = 'INCART' AND ormffundordelstrtyp = 'One Time'
        """,(userid,entityid,))

        print(command)

        cur, dbqerr = db.mydbfunc(con,cur,command)
                            
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="Fund MAX sequence failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)

        con.commit()


        #Fetch the ONE TIME RECORDS for getting orderid from BSE: START
        command = cur.mogrify("select json_agg(b) from (SELECT * FROM webapp.mforderdetails WHERE mfor_ordertype = 'One Time' AND mfor_orderstatus='PNS' AND mfor_pfuserid = %s AND mfor_entityid =%s) as b;",(userid,entityid,))
        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
                                
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="Data for order multiprocess fetch failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        print("cur") 
        print(cur)
        
        #Model to follow in all fetch
        records=[]
        records_orderids=[]
        for record in cur:           
            #print(record[0])
            records = record[0]           
        
        print(records)
        
        for record in records:    
            records_orderids.append(record['mfor_uniquereferencenumber'])

        onetimeorderset = records
        onetimeorderids = records_orderids

        print(onetimeorderset)
        print(onetimeorderids)
        
        print("ontime multiprocessing validation starts")
        pool = Pool(processes=10)
        result = pool.map_async(prepare_order, onetimeorderset)     
        
        #for recc in onetimeorderset:       
        
        print("printing result")
        print(result)

        print("ontime orders processing in progress in other processes.  SIP started in main thread")
        #Fetch the ONE TIME RECORDS for getting orderid from BSE: END
        #select SIP records and enter in order processing table
        print("started with SIP")
        command = cur.mogrify("BEGIN;")
        cur, dbqerr = db.mydbfunc(con,cur,command)
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="DB query failed, BEGIN failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)

        command = cur.mogrify("""
            INSERT INTO webapp.mforderdetails(mfor_prodcuttype,mfor_orormfpflistid,mfor_ororportfolioid,mfor_transactioncode,mfor_ordertype,mfor_buysell,mfor_orderstatus,mfor_transmode,mfor_dptxn,mfor_pfuserid,mfor_clientcode,mfor_schemecd,
            mfor_amount,mfor_kycstatus,mfor_euin,mfor_euinflag,mfor_dpc,mfor_ipadd,mfor_sipstartdate,mfor_freqencytype,mfor_numofinstallment,mfor_foliono,
            mfor_orderoctime,mfor_orderlmtime,mfor_entityid) 
            SELECT orormfprodtype,orormfpflistid,ororportfolioid,orormftrantype,ormffundordelstrtyp,orormfwhattran,'PNS','P','P',ororpfuserid,B.clientcode,orormffndcode,
            ormffundordelsamt,C.lguserkycstatus,'','N','N',C.lguseripaddress,ormffundordelsstdt,ormffundordelsfreq,ormfsipinstal,D.fopfamcfolionumber,
            CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,entityid from webapp.pfmforlist A 
            LEFT OUTER JOIN webapp.uccclientmaster B ON (A.ororpfuserid = B.ucclguserid AND A.entityid = B.uccentityid) 
            LEFT OUTER JOIN webapp.userlogin C ON (A.ororpfuserid = C.lguserid AND A.entityid = C.lgentityid) 
            LEFT OUTER JOIN webapp.mffoliodetails D ON (A.ororfndamcnatcode = D.foamcnatcode AND A.entityid = D.foentityid) 
            where ororpfuserid = %s AND entityid = %s AND ormffndstatus = 'INCART' AND ormffundordelstrtyp = 'SIP'
        """,(userid,entityid,))
                            
        
        print(command)

        cur, dbqerr = db.mydbfunc(con,cur,command)
                            

        command = cur.mogrify("""
            UPDATE webapp.pfmforlist SET ormffndstatus = 'SUBM' WHERE ororpfuserid = %s AND entityid = %s AND ormffndstatus = 'INCART' AND ormffundordelstrtyp = 'SIP'
        """,(userid,entityid,))

        print(command)

        cur, dbqerr = db.mydbfunc(con,cur,command)
                            
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="Fund MAX sequence failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        

        #Call lambda to process SIP : START
        #   Don't wait from lambda response here
        #   YET TO IMPLEMENT
        #       fetch eligible SIP records
        #       call prepare order to do validation and prepare json
        #       send only sucess records to bse and store the responses
        #Call lambda to process SIP : END

        print("end with SIP")
        result.wait()        
        print("end with ontime")
        print(result.get())        
        

        pool.close()
        pool.join()
        con.commit()
        str2=tuple(onetimeorderids)
        print(onetimeorderids)
        print(str2)   
        #Fetch the records with their error message and send it back to front end
        #if no error don't send any record to fronend
        #if error send all the records to front end
        command = cur.mogrify("""
        SELECT json_agg(b) FROM (
            SELECT X.mfor_uniquereferencenumber,Y.orpfportfolioname,Y.orormffundname,X.mfor_amount,X.mfor_valierrors,X.mfor_clientcode FROM webapp.mforderdetails X
            LEFT OUTER JOIN webapp.pfmforlist Y ON (Y.ororportfolioid = X.mfor_ororportfolioid AND Y.orormfpflistid = X.mfor_orormfpflistid AND Y.entityid = X.mfor_entityid)
            WHERE mfor_ordertype = 'One Time' AND mfor_uniquereferencenumber in %s AND mfor_orderstatus = 'VAS' AND mfor_pfuserid = %s AND mfor_entityid =%s ORDER BY Y.orpfportfolioname,Y.orormffundname
            ) AS b;
        """,(str2,userid,entityid,))
        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
                                
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="Validation records fetch failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        print("cur") 
        print(cur)
        
        #Model to follow in all fetch
        suc_records=[]
        for record in cur:
            #print(record)
            suc_records = record[0]
        #print("iam printing records to see")
        
        command = cur.mogrify("""
        SELECT json_agg(b) FROM (
            SELECT X.mfor_uniquereferencenumber,Y.orpfportfolioname,Y.orormffundname,X.mfor_amount,X.mfor_valierrors,X.mfor_clientcode FROM webapp.mforderdetails X
            LEFT OUTER JOIN webapp.pfmforlist Y ON (Y.ororportfolioid = X.mfor_ororportfolioid AND Y.orormfpflistid = X.mfor_orormfpflistid AND Y.entityid = X.mfor_entityid)
            WHERE mfor_ordertype = 'One Time' AND mfor_uniquereferencenumber in %s AND mfor_orderstatus = 'VAF' AND mfor_pfuserid = %s AND mfor_entityid =%s ORDER BY Y.orpfportfolioname,Y.orormffundname
            ) AS b;
        """,(str2,userid,entityid,))
        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
                                
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="Validation records fetch failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        print("cur") 
        print(cur)
        
        #Model to follow in all fetch
        fai_records=[]
        for record in cur:
            #print(record)
            fai_records = record[0]
        #print("iam printing records to see")
        
        resp_recs={
            'success_recs': suc_records,
            'failure_recs': fai_records,
        }

        print(json.dumps(resp_recs))

        cur.close()
        con.close()  

        return json.dumps(resp_recs)


@app.route('/mfordersubmit',methods=['GET','POST','OPTIONS'])
#example for model code http://www.postgresqltutorial.com/postgresql-python/transaction/
def mfordersubmit():
    if request.method=='OPTIONS':
        print ("inside mfordersubmit options")
        return jsonify({'body':'success'})

    elif request.method=='POST':   
        print ("inside mfordersubmit post")

        print(request.headers)
        payload= request.get_json()
        #payload = request.stream.read().decode('utf8')    

        ord_ids=[]
        for payld in payload:
            ord_ids.append(payld['mfor_uniquereferencenumber'])

        str=tuple(ord_ids)
        print(str)
        userid,entityid=jwtnoverify.validatetoken(request)
        con,cur=db.mydbopncon()

        command = cur.mogrify("""
                    SELECT mfor_msgjson FROM webapp.mforderdetails WHERE mfor_uniquereferencenumber IN %s AND mfor_pfuserid = %s AND mfor_entityid = %s and mfor_orderstatus = 'VAS';
                    """,(str,userid,entityid,))
        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="selecting order to submit to BSE failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        
        #Model to follow in all fetch
        orders=[]
        for record in cur:
            print(record[0])
            orders.append(record[0])

        print(orders)
        order_records = json.dumps(orders)

        orderresp = mforderapi.place_order_bse(order_records)
        print(orderresp)
        #Add code to update the order id

        ot_orderids=[]
        sip_orderids=[]

        for orderres in orderresp:
            
            if orderres['success_flag'] == '0':
            
                if orderres['order_type'] == 'OneTime':
                    ot_orderids.append(orderres['trans_no'])
                    command = cur.mogrify("""
                        UPDATE webapp.mforderdetails SET mfor_orderstatus = 'PPY', mfor_orderid = %s, mfor_bseremarks = %s WHERE mfor_uniquereferencenumber = %s AND mfor_pfuserid = %s AND mfor_entityid = %s;
                    """,(orderres['order_id'],orderres['bse_remarks'],orderres['trans_no'],userid,entityid,))
                
                elif orderres['order_type'] == 'SIP':
                    sip_orderids.append(orderres['trans_no'])
                    command = cur.mogrify("""
                        UPDATE webapp.mforderdetails SET mfor_orderstatus = 'INP', mfor_orderid = %s, mfor_bseremarks = %s WHERE mfor_uniquereferencenumber = %s AND mfor_pfuserid = %s AND mfor_entityid = %s;
                    """,(orderres['order_id'],orderres['bse_remarks'],orderres['trans_no'],userid,entityid,))
            
            else:
                if orderres['order_type'] == 'OneTime':
                    ot_orderids.append(orderres['trans_no'])
                    command = cur.mogrify("""
                        UPDATE webapp.mforderdetails SET mfor_orderstatus = 'FAI', mfor_valierrors = %s WHERE mfor_uniquereferencenumber = %s AND mfor_pfuserid = %s AND mfor_entityid = %s;
                    """,(orderres['bse_remarks'],orderres['trans_no'],userid,entityid,))

                elif orderres['order_type'] == 'SIP':
                    sip_orderids.append(orderres['trans_no'])
                    command = cur.mogrify("""
                        UPDATE webapp.mforderdetails SET mfor_orderstatus = 'FAI', mfor_valierrors = %s WHERE mfor_uniquereferencenumber = %s AND mfor_pfuserid = %s AND mfor_entityid = %s;
                    """,(orderres['bse_remarks'],orderres['trans_no'],userid,entityid,))

            print(command)

            cur, dbqerr = db.mydbfunc(con,cur,command)
            con.commit()

            '''       
            Do Not send any response for DB update failures.                         
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="Fund MAX sequence failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            '''
        if orderres['order_type'] == 'OneTime':
            str2 = tuple(ot_orderids)           

            command = cur.mogrify("""
            SELECT json_agg(b) FROM (
                SELECT X.mfor_uniquereferencenumber,Y.orpfportfolioname,Y.orormffundname,X.mfor_amount,X.mfor_orderid,X.mfor_clientcode FROM webapp.mforderdetails X
                LEFT OUTER JOIN webapp.pfmforlist Y ON (Y.ororportfolioid = X.mfor_ororportfolioid AND Y.orormfpflistid = X.mfor_orormfpflistid AND Y.entityid = X.mfor_entityid)
                WHERE mfor_ordertype = 'One Time' AND mfor_uniquereferencenumber in %s AND mfor_orderstatus = 'PPY' AND mfor_pfuserid = %s AND mfor_entityid =%s ORDER BY Y.orpfportfolioname,Y.orormffundname
                ) AS b;
            """,(str2,userid,entityid,))
            print(command)
            cur, dbqerr = db.mydbfunc(con,cur,command)
                                    
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="Validation records fetch failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            print("cur") 
            print(cur)
            
            #Model to follow in all fetch
            suc_records=[]
            for record in cur:
                #print(record)
                suc_records = record[0]
            #print("iam printing records to see")
            
            command = cur.mogrify("""
            SELECT json_agg(b) FROM (
                SELECT X.mfor_uniquereferencenumber,Y.orpfportfolioname,Y.orormffundname,X.mfor_amount,X.mfor_valierrors,X.mfor_clientcode FROM webapp.mforderdetails X
                LEFT OUTER JOIN webapp.pfmforlist Y ON (Y.ororportfolioid = X.mfor_ororportfolioid AND Y.orormfpflistid = X.mfor_orormfpflistid AND Y.entityid = X.mfor_entityid)
                WHERE mfor_ordertype = 'One Time' AND mfor_uniquereferencenumber in %s AND mfor_orderstatus = 'FAI' AND mfor_pfuserid = %s AND mfor_entityid =%s ORDER BY Y.orpfportfolioname,Y.orormffundname
                ) AS b;
            """,(str2,userid,entityid,))
            print(command)
            cur, dbqerr = db.mydbfunc(con,cur,command)
                                    
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="Validation records fetch failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            print("cur") 
            print(cur)
            
            #Model to follow in all fetch
            fai_records=[]
            for record in cur:
                #print(record)
                fai_records = record[0]
            #print("iam printing records to see")
            
            resp_recs={
                'success_recs': suc_records,
                'failure_recs': fai_records,
            }

            print(json.dumps(resp_recs))

            cur.close()
            con.close()  

        elif orderres['order_type'] == 'SIP':
            resp_recs = {
                'status' : 'completed',
                'sip_orderids': sip_orderids
                }

    return json.dumps(resp_recs)





@app.route('/mforderpayment',methods=['GET','POST','OPTIONS'])
def mforderpayment():
    if request.method=='OPTIONS':
        print ("inside mforderpayment options")
        return jsonify({'body':'success'})

    elif request.method=='POST':   
        print ("inside mforderpayment post")

        print(request.headers)
        payload= request.get_json()
        #payload = request.stream.read().decode('utf8')    
        print(payload)

        ord_ids=[]
        total_amt = 0
        for payld in payload:
            ord_ids.append(payld['mfor_orderid'])
            total_amt = total_amt + payld['mfor_amount']

        # userid,entityid=jwtnoverify.validatetoken(request)
        print(payload[0]['mfor_clientcode'])
        
        record_to_submit = {
            'client_code' : payload[0]['mfor_clientcode'],
            'transaction_ids' : ord_ids,
            'total_amt': total_amt
        }
        
        # FOR BSE PAYMENT LINK : START
        url_pay=mforderapi.get_payment_link_bse1(record_to_submit)
        #Code to be re-written to include http call
        '''
        url=settings.BSESTAR_USERCREATION_URL[settings.LIVE];
        print(url)
        print(record_to_submit)
        
        r = requests.post(url, json=record_to_submit)
        print(r.text)
        url_pay= json.loads(r.text)   
        print('url_pay :',url_pay)     
        '''
        # FOR BSE PAYMENT LINK : END
        
        # FOR DIRECT BANK PAYMENT LINK
        #url_pay=mforderapi.get_payment_link_bse(record_to_submit)
        
        #return status from get_payment_link_bse1
        if((url_pay['status'] == 'success') and (url_pay['url_type'] == 'bsepayurl')):
            print("url_pay")
            print(type(url_pay['payment_url']))
            returns = {'html' : url_pay['payment_url']}
            return jsonify(returns)
        else:        
            return url_pay

        ##return status from get_payment_link_bse
        if((url_pay['status'] == 'success') and (url_pay['url_type'] == 'directbnkurl')):
            pass
        else:
            pass
        
        
        #r = Response(response=url_pay, status=200, mimetype="text/html")
        #r.headers["Content-Type"] = "text/html; charset=utf-8"
        #return r
        #return url_pay, 200, {'Content-Type': 'text/html; charset=utf-8'}
        '''
        con,cur=db.mydbopncon()





        command = cur.mogrify("""
                    SELECT mfor_msgjson FROM webapp.mforderdetails WHERE mfor_uniquereferencenumber IN %s AND mfor_pfuserid = %s AND mfor_entityid = %s;
                    """,(str,userid,entityid,))
        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="DB query failed, BEGIN failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)
        
        #Model to follow in all fetch
        orders=[]
        for record in cur:
            print(record[0])
            orders.append(record[0])

        print(orders)
        one_time_records = json.dumps(orders)
    
        return "ok"
        '''


def dateformat1(datestr):
#code to convert the date from UTC to IST
    if (datestr is not None):    
        if(datestr[-1:] == 'Z'):
            print(datetime.strptime(datestr, "%Y-%m-%dT%H:%M:%S.%fZ"))
            utc = datetime.strptime(datestr, "%Y-%m-%dT%H:%M:%S.%fZ")
            from_zone = tz.tzutc()
            to_zone = tz.tzlocal()
            utc = utc.replace(tzinfo=from_zone)
            # Convert time zone
            central = utc.astimezone(to_zone)
            centralstr=central.strftime('%Y-%m-%d')
            print(centralstr)
            return centralstr
        elif(isinstance(datestr, str)):
            print("inside date string")
            print(datestr)
            datef = datetime.strptime(datestr, '%d-%b-%Y')            
            datefrm = datetime.strftime(datef, "%d/%m/%Y")
            print(datefrm)
            return datefrm
        else:
            return datestr


# Main function to prepare and submit Transaction to BSE
def prepare_order(orderrecord):
    ord=orderrecord
    print("processing order" + ord['mfor_uniquereferencenumber'])
    #time.sleep(0.5)
    #return json.dumps({'mfor_uniquereferencenumber': ord['mfor_uniquereferencenumber'],'order_id': '','amount':ord['mfor_amount']})
    
    if(ord['mfor_ordertype'] == 'One Time'):
        has_error, order_json = prepare_onetime_ord(ord)
        print("back from order prep")
        print(has_error)
        print(order_json)
        '''
        if has_error:
            pass
        else:
            #CALL ORDER PLACEMENT API to place order
            #order_id = <value returned from BSE>
            
            print(order_json)
            orderresp = mforderapi.place_order_bse(order_json)
            if (orderresp['success_flag'] == '0'):
                orderstat = 'PPY'
                order_id = orderresp['order_id']
            else:
                has_error = True
                orderstat = 'FAI'
        '''
    elif(ord['mfor_ordertype'] == 'SIP'):
        has_error, order_json = prepare_isip_ord(ord)
        '''
        if has_error:
            pass
        else:
            #CALL ORDER PLACEMENT API to place order
            #order_id = <value returned from BSE>
            orderstat = 'INP'
        '''
    con,cur=db.mydbopncon()
    '''
    (True , errormsg)
    ( False, json.dumps(data_dict))
    '''

    if has_error:
        orderstat = 'VAF'  #Validation failed
        print(order_json)
        print(orderstat)
        print(ord['mfor_uniquereferencenumber'])
        print(ord['mfor_pfuserid'])
        print(ord['mfor_entityid'])

        command = cur.mogrify("""
            UPDATE webapp.mforderdetails SET mfor_valierrors = %s, mfor_orderstatus = %s WHERE mfor_uniquereferencenumber = %s AND mfor_pfuserid = %s AND mfor_entityid = %s;
            """,(order_json,orderstat,ord['mfor_uniquereferencenumber'],ord['mfor_pfuserid'],ord['mfor_entityid'],))

        print(command)

        cur, dbqerr = db.mydbfunc(con,cur,command)
        
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="Fund MAX sequence failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)

        print("order unqrecord id :" + ord['mfor_uniquereferencenumber'] + ", has validation errors")
    
    else:
        
        print("printing records to check")
        orderstat = 'VAS'  #Validation Successful then store the JSON
        print(order_json)
        print(orderstat)
        print(ord['mfor_uniquereferencenumber'])
        print(ord['mfor_pfuserid'])
        print(ord['mfor_entityid'])
        #update the order id in the table
        command = cur.mogrify("""
            UPDATE webapp.mforderdetails SET mfor_msgjson = %s, mfor_orderstatus = %s WHERE mfor_uniquereferencenumber = %s AND mfor_pfuserid = %s AND mfor_entityid = %s;
        """,(order_json,orderstat,ord['mfor_uniquereferencenumber'],ord['mfor_pfuserid'],ord['mfor_entityid'],))

        print(command)

        cur, dbqerr = db.mydbfunc(con,cur,command)

        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="Fund MAX sequence failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)

        print("order unqrecord id :" + ord['mfor_uniquereferencenumber'] + ", has passed validation")

    con.commit()                                
    cur.close()
    con.close()      

    return json.dumps({'mfor_uniquereferencenumber': ord['mfor_uniquereferencenumber'],'order_status': orderstat,'amount':ord['mfor_amount']})
    


# function to VALIDATE and CREATE data for one time order
def prepare_onetime_ord(ord):
    #Onetime PURCHASE OR REDEMPTION ORDERS
    haserror = False
    #Create error messages for the fieds which are NOT NULL IN DB but mandatory in the message
    errormsg = ''

    # Fill all fields for a FRESH PURCHASE
    # Change fields if its a redeem or addl purchase
    data_dict = {
        'trans_code': ord['mfor_transactioncode'],
        'trans_no': int(ord['mfor_uniquereferencenumber']),
        'scheme_cd': ord['mfor_schemecd'],
        'client_code': ord['mfor_clientcode'],        
        'dptxn_mode' : ord['mfor_dptxn'],        
        'dpc_flg' : 'N',
        'param2' : '',
        'param3' : '',
        'mfor_ordertype': 'OneTime'
    }
    
    
    if(ord['mfor_internalrefnum']):
        data_dict['internal_transaction'] = ord['mfor_internalrefnum']
    else:
        data_dict['internal_transaction'] = '' 

    if(ord['mfor_subbrcode']):
        data_dict['subbr_code'] = ord['mfor_subbrcode']
    else:
        data_dict['subbr_code'] = '' 

    if(ord['mfor_subbrokerarn']):
        data_dict['subbr_arn'] = ord['mfor_subbrokerarn']
    else:
        data_dict['subbr_arn'] = '' 

    if(ord['mfor_euin']):
        data_dict['euin'] = ord['mfor_euin']
    else:
        data_dict['euin'] = ''    

    if(ord['mfor_euinflag']):
        data_dict['euin_flg'] = ord['mfor_euinflag']
    else:
        data_dict['euin_flg'] = ''    

    if(ord['mfor_ipadd']):
        data_dict['ipadd'] = ord['mfor_ipadd']
    else:
        data_dict['ipadd'] = ''

    if(ord['mfor_foliono']):
        data_dict['folio_no'] = ord['mfor_foliono']
    else:
        data_dict['folio_no'] = ''

    if(ord['mfor_kycstatus']):
        data_dict['kyc_status'] = ord['mfor_kycstatus']
    else:
        haserror = True
        errormsg = errormsg + "Missing KYC status: " 

    print(ord['mfor_buysell'])

    if (ord['mfor_buysell'] == 'P'):        
        # PURCHASE transaction        
        data_dict['buy_sell'] = 'P'
        data_dict['order_id'] = ''

        if(ord['mfor_amount']):
            data_dict['order_amt'] = ord['mfor_amount']
        else:
            haserror = True
            errormsg = errormsg + "Missing ORDER amount: " 

        data_dict['order_qty'] = ''
        data_dict['all_redeem'] = 'N'
        data_dict['remarks'] = ''
        data_dict['min_redeem'] = 'N'
        

        #CHECK IN HOLDINGS TABLE FOR EXISTING FUND UNDER THIS PORTFOLIO
        #IF WE HAVE FUND HOLDING THEN trans_code = 'ADDITIONAL' ELSE it is 'FRESH'
        data_dict['buy_sell_type'] = 'FRESH'    
        

    elif (ord['mfor_buysell'] == 'R'):
        # REDEEM transaction
        ## set folio_no by looking at previous transactions
        '''
        trans_l = get_previous_trans(transaction)

        ### assumption: pick the first relevant transaction's folio number if there are multiple transactions 
        # data_dict['folio_no'] = '123456789012345'
        data_dict['folio_no'] = trans_l[0].folio_number

        if (transaction.transaction_type == 'A'):
            # ADDITIONAL PURCHASE order
            data_dict['buy_sell_type'] = 'ADDITIONAL'
            data_dict['order_val'] = int(transaction.amount)
        
        elif (transaction.transaction_type == 'R'):
            # REDEEM order
            data_dict['buy_sell'] = 'R'

            ## set all_redeem flag in case entire investment is being redeemed, else 
            if (transaction.all_redeem):
                data_dict['all_redeem'] = 'Y'
                data_dict['order_val'] = ''
            elif (transaction.all_redeem == None):
                raise Exception(
                    "Internal error 634: all_redeem field of internal transaction table is not set for a redeem transaction"
        '''
        pass
    print('####################')
    print(data_dict)
    print('####################')
    print(haserror)
    if haserror:
        return (True , errormsg)
    else:
        return( False, json.dumps(data_dict))

# function to VALIDATE and CREATE data for ISIP order
def prepare_isip_ord(ord):
    #Prepares ISIP order

    haserror = False
    errormsg = ''
    # Fill all fields for a ISIP creation
    # Change fields if its a redeem or addl purchase
    data_dict = {
        'trans_code': ord['mfor_transactioncode'],
        'trans_no': ord['mfor_uniquereferencenumber'],        
        'scheme_cd': ord['mfor_schemecd'],
        'client_code': ord['mfor_uniquereferencenumber'],
        'trans_mode' : ord['mfor_transmode'],   #D/P
        'dptxn_mode' : ord['mfor_dptxn'],       #C/N/P (CDSL/NSDL/PHYSICAL)
        'freq_allowed' : 1,
        'Remarks' : '',
        'first_ord_flg' : 'N',
        'borkerage' : '',
        'xsip_mandate_id' : '',
        'dpc_flg' : 'N',
        'xsip_reg_id' : '',        
        'Param3' : '',
        'mfor_ordertype': 'SIP'
    }

    if(ord['mfor_internalrefnum']):
        data_dict['internal_transaction'] = ord['mfor_internalrefnum']
    else:
        data_dict['internal_transaction'] = '' 


    strdt = dateformat1(ord['mfor_sipstartdate'])
    if(strdt):
        data_dict['start_date'] = strdt
    else:
        haserror = True
        errormsg = errormsg + "Missing SIP start date: "        
    
    if(ord['mfor_freqencytype']):
        data_dict['freq_type'] = ord['mfor_freqencytype']
    else:
        haserror = True
        errormsg = errormsg + "Missing SIP frequency: " 

    if(ord['mfor_amount']):
        data_dict['order_amt'] = ord['mfor_amount']
    else:
        haserror = True
        errormsg = errormsg + "Missing SIP amount: " 

    if(ord['mfor_numofinstallment']):
        data_dict['num_of_instalment'] = ord['mfor_numofinstallment']
    else:
        haserror = True
        errormsg = errormsg + "Missing instalment numbers: " 


    if(ord['mfor_foliono']):
        data_dict['folio_no'] = ord['mfor_foliono']
    else:
        data_dict['folio_no'] = ''

    if(ord['mfor_sipmandateid']):
        data_dict['isip_mandate_id'] = ord['mfor_sipmandateid']
    else:
        haserror = True
        errormsg = errormsg + "Missing ISIP Mandate id: " 

    if(ord['mfor_subbrcode']):
        data_dict['subbr_code'] = ord['mfor_subbrcode']
    else:
        data_dict['subbr_code'] = '' 

    if(ord['mfor_subbrokerarn']):
        data_dict['subbr_arn'] = ord['mfor_subbrokerarn']
    else:
        data_dict['subbr_arn'] = '' 

    if(ord['mfor_euin']):
        data_dict['euin'] = ord['mfor_euin']
    else:
        data_dict['euin'] = ''    

    if(ord['mfor_euinflag']):
        data_dict['euin_flg'] = ord['mfor_euinflag']
    else:
        data_dict['euin_flg'] = ''    

    if(ord['mfor_ipadd']):
        data_dict['ipadd'] = ord['mfor_ipadd']
    else:
        data_dict['ipadd'] = ''

    if haserror:
        return (True , errormsg)
    else:
        return( False, json.dumps(data_dict))


# function to VALIDATE and CREATE data for ISIP order
def prepare_pay_lnk_rec(ord):
    #Prepares record to get payment link
    haserror = False




@app.route('/orpost',methods=['GET','POST','OPTIONS'])
def orpost():
    if request.method=='OPTIONS':
        print ("inside orderapi options")
        return 'inside orderapi options'

    elif request.method=='POST' :
        print("inside orderapi POST")

        print((request))        
        #userid,entityid=jwtnoverify.validatetoken(request)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        payload= request.values
        #payload=json.loads(payload)
        print(payload)
        bse_order = 'nat'
        #bse_order = json.loads(payload)
        print(bse_order)
        return bse_order
