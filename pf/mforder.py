from pf import app
from pf import dbfunc as db
from pf import jwtdecodenoverify as jwtnoverify
from pf import mforderpaystatus_bg as bg
from pf import webapp_settings
from pf import mforderapi
from pf import mfsiporder

from datetime import datetime, date, timedelta
from multiprocessing import Process
from multiprocessing import Pool
import json
import time
import calendar

from flask import request, make_response, jsonify, Response, redirect
import psycopg2
import requests
import jwt
from dateutil import tz

@app.route('/mforderdatafetch',methods=['POST','OPTIONS'])
def mforderdatafetch():
#This is called by fund data fetch service
    if request.method=='OPTIONS':
        print("inside pforderdatafetch options")
        return make_response(jsonify('inside FUNDDATAFETCH options'), 200)  

    elif request.method=='POST':
        print("inside pforderdatafetch POST")
        print((request))        
        print(request.headers)
        userid,entityid=jwtnoverify.validatetoken(request)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        print(userid,entityid)
        payload= request.get_json()
        print(payload)
        
        prod = payload.get('prod',None)
        trantype = payload.get('trantype',None)
        status  = None 
        failreason = None

        if prod == None:
            status = "datafail"
            if failreason:
                failreason = failreason + "product type not sent|"
            else:
                failreason = "product type not sent|"
        if trantype == None:
            status = "datafail"
            if failreason:
                failreason = failreason + "Transaction type not sent|"
            else:
                failreason = "Transaction type not sent|"

        if trantype == "buy":
            whattrantype = 'P'
        elif trantype == "sell":
            whattrantype = 'R'

        fndstatus = 'INCART'


        print('after')
        #time.sleep(1)
        record=None

        if status == None:
            con,cur=db.mydbopncon()
            
            print(con)
            print(cur)
            
            #cur.execute("select row_to_json(art) from (select a.*, (select json_agg(b) from (select * from pfstklist where pfportfolioid = a.pfportfolioid ) as b) as pfstklist, (select json_agg(c) from (select * from pfmflist where pfportfolioid = a.pfportfolioid ) as c) as pfmflist from pfmaindetail as a where pfuserid =%s ) art",(userid,))
            #command = cur.mogrify("select row_to_json(art) from (select a.*,(select json_agg(b) from (select * from webapp.pfstklist where pfportfolioid = a.pfportfolioid ) as b) as pfstklist, (select json_agg(c) from (select c.*,(select json_agg(d) from (select * from webapp.pfmforlist where orormflistid = c.ormflistid AND ormffndstatus='INCART' AND entityid=%s) as d) as ormffundorderlists from webapp.pfmflist c where orportfolioid = a.pfportfolioid ) as c) as pfmflist from webapp.pfmaindetail as a where pfuserid =%s AND entityid=%s) art",(entityid,userid,entityid,))
            command = cur.mogrify(
                """
                WITH portport as (select ororportfolioid,orormflistid,orormfpflistid from webapp.pfmforlist where ormffndstatus = %s AND orormfprodtype = %s AND orormfwhattran = %s AND ororpfuserid = %s AND entityid = %s) 
                select json_agg(art) from (
                select a.*,
                (select json_agg(b) from (select * from webapp.pfstklist where pfportfolioid = a.pfportfolioid ) as b) as pfstklist, 
                (select json_agg(c) from 
                    (select c.*,
                        (select json_agg(d) from 
                            (select * from webapp.pfmforlist 
                                where orormflistid in (SELECT distinct orormflistid FROM PORTPORT) 
                                AND ororportfolioid =a.pfportfolioid AND orormflistid=c.ormflistid 
                                AND ormffndstatus = %s  AND orormfwhattran = %s
                                AND entityid = %s ORDER BY ormffundordelstrtyp
                            ) as d
                        ) as ormffundorderlists 
                    from webapp.pfmflist c where ormflistid in (SELECT distinct orormflistid FROM portport) AND  entityid = %s AND orportfolioid =a .pfportfolioid 
                    ) as c
                ) as pfmflist 
                from webapp.pfmaindetail as a where pfuserid = %s AND entityid = %s AND pfportfolioid IN (SELECT distinct ororportfolioid FROM portport) ORDER BY pfportfolioid  ) art
                """,(fndstatus,prod,whattrantype,userid,entityid,fndstatus,whattrantype,entityid,entityid,userid,entityid,))

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
                    status = "dbfail"
                    failreason = "order data fetch failed with DB error"
                    print(status,failreason)

            if cur.rowcount > 1:
                status = "dbfail"
                failreason = "order data fetch returned more rows"
                print(status,failreason)

            if cur.rowcount == 1:
                record = cur.fetchall()[0][0]
                print(record) 
   
        print("order details returned for user: "+ userid + "  product :" + prod + " trantype: " + trantype)

        orderdata = {
        'orderdata'   :     [] if record == None else record,
        'status'      :     'success' if status == None else status,
        'failreason'  :     '' if failreason == None else failreason
        }

        if orderdata['status'] == "success":
            return make_response(jsonify(orderdata), 200)
        else:
            return make_response(jsonify(orderdata), 400)

@app.route('/mfordersave',methods=['GET','POST','OPTIONS'])
#example for model code http://www.postgresqltutorial.com/postgresql-python/transaction/
def mfordersave():
    
    if request.method=='OPTIONS':
        print ("inside mfordersave options")
        return jsonify({'body':'success'})

    elif request.method=='POST':   
        print ("inside mfordersave post")
        print("--------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        print(request.content_length)
        print("--------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        print(request.headers)
        payload= request.get_json()
        #payload = request.stream.read().decode('utf8')    
        
        pfdatas = payload
        print(pfdatas)
        
        userid,entityid=jwtnoverify.validatetoken(request)

        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        con,cur=db.mydbopncon()

        command = cur.mogrify("BEGIN;")
        cur, dbqerr = db.mydbfunc(con,cur,command)
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="DB query failed, BEGIN failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)

        savetimestamp = datetime.now()
        pfsavedate = savetimestamp.strftime('%Y%m%d') 
        pfsavetimestamp=savetimestamp.strftime('%Y/%m/%d %H:%M:%S')
        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        for pfdata in pfdatas:
            pfmflsdatalist=[]
            pfmforlsdatalist=[]
            print("pfdata before removing")
            print(pfdata)
            savetype = None
            
            #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~            
            if 'pfportfolioid' in pfdata:
                if pfdata.get('pfportfolioid') == "NEW":
                    savetype = "New"
                else:
                    savetype = "Old"
            else:
                #if 'pfportfolioid' itself not in the data it is error we shouuld exit
                print('pfportfolioid is not in the messages')
                return jsonify({'natstatus':'error','statusdetails':'Data error (Portfolio id missing)'})
            #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~            
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
            
            incartscreens = {'BSEMFbuy','BSEMFsell'}

            if'pfscreen' in pfdata:
                screenid= pfdata.get('pfscreen',None)
                if screenid == "pfs":
                    filterstr="NEW"
                elif screenid in incartscreens:
                    filterstr="INCART"
                else:
                    filterstr="INCART"

            else:
                screenid = None
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
                print('inside old line188')
                pfdata['pflmtime']= pfsavetimestamp
                pfdata.get('pfuserid')            

                #If request is from pfscreen then we update pf details, if it is from order screen skip this.
                
                ###PF stock details update START###
                    #NO STOCK DETAILS FOR THIS FUNCTION TO HANDLE
                ###PF stock details update END###

                ###PF MF details update START###
                print(pfmflsdata)
                if pfmflsdata!=None:
                    i = 0
                    print("inside pfmflsdata !=None line201")
                    print(pfmflsdata)
                    print("inside pfmflsdata !=None line201")

                    for d in pfmflsdata:
                        print("inside for test loop ln 205")
                        print(d)
                        print(i)
                        i = i+1

                    for d in pfmflsdata: 
                        print(d)
                        print("pfmflsdata inside for")
                        print(d)
                        d['ormfoctime']= pfsavetimestamp
                        d['ormflmtime']= pfsavetimestamp
                        
                        command = cur.mogrify("SELECT ormflistid FROM webapp.pfmflist WHERE ormffndcode = %s AND orpfuserid = %s AND orportfolioid = %s AND entityid =%s;",(d.get('ormffndcode'),userid,pfdata.get('pfportfolioid'),entityid,))
                        print(command)
                        cur, dbqerr = db.mydbfunc(con,cur,command)
                                            
                        if cur.closed == True:
                            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                                dbqerr['statusdetails']="Fund MAX sequence failed"
                            resp = make_response(jsonify(dbqerr), 400)
                            return(resp)

                        #Model to follow in all fetch
                        if cur.rowcount == 1:
                            for record in cur:  
                                d['ormflistid'] = record[0]                                

                        elif cur.rowcount == 0:
                            print("Fund doesn't exist in this users portfolio")
                            d['ormflistid'] = ""
                        else:
                            dbqerr = {'natstatus': 'error', 'statusdetails': 'Same fund exists multiple times in the portfolio'}
                            return(make_response(jsonify(dbqerr), 400))
                        
                        print("is the fund already exists:")
                        print(d['ormflistid'])
                        
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
                                                                   
                                    e['ormfoctime']= pfsavetimestamp
                                    e['ormflmtime']= pfsavetimestamp
                                    e['orormffundname']=d.get('ormffundname')
                                    e['orormffndcode']=d.get('ormffndcode')
                                    e['orormflistid'] = d.get('ormflistid')
                                    e['entityid']=entityid
                                    e['ororportfolioid']=pfdata.get('pfportfolioid')
                                    e['orpfportfolioname']=pfdata.get('pfportfolioname')
                                    e['ororpfuserid']=d.get('orpfuserid')


                                    print("PRINTING e")
                                    print(e)  

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
                                        e['orormfpflistid']= "or"+d.get('ormflistid')+str(pfmforlsseqnum)
                                        e['orormfseqnum'] = str(pfmforlsseqnum)

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

                                            print(command)
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
        
            #POST UPDATES COMMON:START 
            # (source: mforder.py -> mfordersave; referredin: portfolio.py ->executepf,pfdatasave )
            # Fund edit/delete allowed : START
            #If atleast one of the order is not new, we should not allow the fund to be removed and edited
            #in this case we mark ormffndnameedit as fixed    
            
            command = cur.mogrify("UPDATE webapp.pfmflist SET ormffndnameedit = 'fixed' WHERE ormflistid in (SELECT distinct orormflistid FROM webapp.pfmforlist WHERE UPPER(ormffndstatus) IN ('INCART') and ororpfuserid = %s AND entityid = %s);",(userid,entityid,))
            print(command)

            cur, dbqerr = db.mydbfunc(con,cur,command)
                                
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="Fund MAX sequence failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)

            #command = cur.mogrify("UPDATE webapp.pfmflist SET ormffndnameedit = 'noedit' WHERE ormflistid in (SELECT distinct orormflistid FROM webapp.pfmforlist WHERE UPPER(ormffndstatus) = 'NEW' and ororpfuserid = %s AND entityid = %s) AND 0 = (SELECT COUNT( distinct orormflistid) FROM webapp.pfmforlist WHERE UPPER(ormffndstatus) != 'NEW' and ororpfuserid = %s AND entityid = %s);",(userid,entityid,userid,entityid,))
            command = cur.mogrify("UPDATE webapp.pfmflist SET ormffndnameedit = 'noedit' WHERE ormflistid NOT IN (SELECT distinct orormflistid FROM webapp.pfmforlist WHERE UPPER(ormffndstatus) IN ('INCART') and ororpfuserid = %s AND entityid = %s);",(userid,entityid,))
            print(command)

            cur, dbqerr = db.mydbfunc(con,cur,command)
                                
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="Fund MAX sequence failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            # Fund edit/delete allowed : END

            #POST UPDATES COMMON:END



            #do the clean up of funds removed: START
            pfid = pfdata.get('pfportfolioid')
            if pfmflsdatalist:                
                #command = cur.mogrify("DELETE FROM webapp.pfmflist where ormflistid NOT IN %s AND entityid =%s AND orpfuserid=%s AND orportfolioid= %s AND ormffndnameedit in ('edit','noedit');",(str2,entityid,userid,pfdata.get('pfportfolioid'),))
                command = cur.mogrify("""
                            DELETE FROM webapp.pfmflist where ormflistid NOT IN %s 
                            AND ormflistid NOT IN (SELECT DISTINCT orormflistid FROM webapp.pfmforlist WHERE entityid =%s AND ororpfuserid= %s)
                            AND entityid =%s AND orpfuserid=%s AND ormffndnameedit in ('edit','noedit');                           
                            """
                            ,(str2,entityid,userid,entityid,userid,))
                            #AND ormffndnameedit in ('edit','noedit');

                print(command)
            else:
                #command = cur.mogrify("DELETE FROM webapp.pfmflist where entityid =%s AND orpfuserid=%s AND orportfolioid= %s;",(entityid,userid,pfid,))
                command = cur.mogrify("""
                            DELETE FROM webapp.pfmflist 
                            WHERE ormflistid NOT IN (SELECT DISTINCT orormflistid FROM webapp.pfmforlist WHERE entityid =%s AND ororpfuserid= %s)
                            AND entityid =%s AND orpfuserid=%s AND ormffndnameedit in ('edit','noedit');
                            """
                            ,(entityid,userid,entityid,userid,))
                            #

                print(command)

            cur, dbqerr = db.mydbfunc(con,cur,command)
                                
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="Fund MAX sequence failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            
            #remove the fund where we don't have the any entry for order :START
            if pfmflsdatalist:
                command = cur.mogrify("""
                        DELETE FROM webapp.pfmflist where ormflistid IN 
                        (SELECT A.ormflistid FROM webapp.pfmflist A LEFT JOIN webapp.pfmforlist B ON A.ormflistid = B.orormflistid 
                            WHERE B.orormflistid IS NULL AND A.ormflistid IN %s AND A.entityid = %s) AND entityid =%s AND orpfuserid=%s AND orportfolioid= %s;
                        """,(str2,entityid,entityid,userid,pfid,))

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
        payload_org= request.get_json()
        #payload = request.stream.read().decode('utf8')    
        print(payload_org)

        one_time_pay_details = payload_org['one_time_pay']
        sip_pay_details = payload_org['sip_pay']  #Not required for one time
        payload = payload_org['succrecs']
        
        screenid = payload_org.get('screenid', None)
        if screenid == "ordBSEMFbuy":
            delstrtyp = 'One Time'
        elif screenid == "ordBSEMFsell":
            delstrtyp = 'BSMFsell'

        if sip_pay_details is None or sip_pay_details == '':
            sip_pay_details = {}
            sip_pay_details['mandate_id'] = ''
            sip_pay_details['mandate_type'] = '' 


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
            INSERT INTO webapp.mforderdetails (mfor_producttype,mfor_orormfpflistid,mfor_ororportfolioid,mfor_transactioncode,mfor_ordertype,mfor_buysell,mfor_orderstatus,
            mfor_transmode,mfor_dptxn,mfor_pfuserid,mfor_clientcode,mfor_schemecd,mfor_amount,mfor_qty,mfor_foliono,mfor_kycstatus,mfor_euin,mfor_euinflag,mfor_dpc,mfor_ipadd,
            mfor_orderoctime,mfor_orderlmtime,mfor_entityid,mfor_memberid,mfor_subbrcode,mfor_subbrokerarn) 
            SELECT orormfprodtype,orormfpflistid,ororportfolioid,orormftrantype,ormffundordelstrtyp,orormfwhattran,'PNS',
            'P','P',ororpfuserid,B.clientcode,orormffndcode,ormffundordelsamt,ormffundordunit,D.fopfamcfolionumber,C.lguserkycstatus,'','N','N',C.lguseripaddress,
            CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,entityid,'','','' from webapp.pfmforlist A 
            LEFT OUTER JOIN webapp.uccclientmaster B ON (A.ororpfuserid = B.ucclguserid AND A.entityid = B.uccentityid) 
            LEFT OUTER JOIN webapp.userlogin C ON (A.ororpfuserid = C.lguserid AND A.entityid = C.lgentityid) 
            LEFT OUTER JOIN webapp.mffoliodetails D ON (A.ororfndamcnatcode = D.foamcnatcode AND A.entityid = D.foentityid) 
            where ororpfuserid = %s AND entityid = %s AND ormffndstatus = 'INCART' AND ormffundordelstrtyp = %s;
        """,(userid,entityid,delstrtyp,))

        print(command)


        cur, dbqerr = db.mydbfunc(con,cur,command)
                            
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="Fund MAX sequence failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)


        command = cur.mogrify("""
            UPDATE webapp.pfmforlist SET ormffndstatus = 'SUBM' WHERE ororpfuserid = %s AND entityid = %s AND ormffndstatus = 'INCART' AND ormffundordelstrtyp = %s
        """,(userid,entityid,delstrtyp,))

        print(command)

        cur, dbqerr = db.mydbfunc(con,cur,command)
                            
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="Fund MAX sequence failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)

        con.commit()


        #Fetch the ONE TIME RECORDS for getting orderid from BSE: START
        command = cur.mogrify("select json_agg(b) from (SELECT * FROM webapp.mforderdetails WHERE mfor_ordertype = %s AND mfor_orderstatus='PNS' AND mfor_pfuserid = %s AND mfor_entityid =%s) as b;",(delstrtyp,userid,entityid,))
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
        if cur:
            for record in cur:           
                #print(record[0])
                records = record[0]           
        
        if records is None:
            records=[]

        print(records)
        
        has_ontime_record = True

        if len(records) < 1:
            has_ontime_record = False

        print("has_ontime_record")
        print(has_ontime_record)
        if has_ontime_record:
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
            print(sip_pay_details)
            print(one_time_pay_details)

        print("ontime orders processing in progress in other processes.  SIP started in main thread")
        #Fetch the ONE TIME RECORDS for getting orderid from BSE: END
        
        if screenid == "ordBSEMFbuy":
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
                INSERT INTO webapp.mforderdetails(mfor_producttype,mfor_orormfpflistid,mfor_ororportfolioid,mfor_transactioncode,mfor_ordertype,mfor_buysell,mfor_orderstatus,mfor_transmode,mfor_dptxn,mfor_pfuserid,mfor_clientcode,mfor_schemecd,
                mfor_amount,mfor_kycstatus,mfor_euin,mfor_euinflag,mfor_dpc,mfor_ipadd,mfor_sipstartdate,mfor_freqencytype,mfor_numofinstallment,mfor_foliono,
                mfor_orderoctime,mfor_orderlmtime,mfor_entityid,mfor_sipmandateid,mfor_sipmandatetype) 
                SELECT orormfprodtype,orormfpflistid,ororportfolioid,orormftrantype,ormffundordelstrtyp,orormfwhattran,'PNS','P','P',ororpfuserid,B.clientcode,orormffndcode,
                ormffundordelsamt,C.lguserkycstatus,'','N','N',C.lguseripaddress,ormffundordelsstdt,ormffundordelsfreq,ormfsipinstal,D.fopfamcfolionumber,
                CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,entityid,%s,%s from webapp.pfmforlist A 
                LEFT OUTER JOIN webapp.uccclientmaster B ON (A.ororpfuserid = B.ucclguserid AND A.entityid = B.uccentityid) 
                LEFT OUTER JOIN webapp.userlogin C ON (A.ororpfuserid = C.lguserid AND A.entityid = C.lgentityid) 
                LEFT OUTER JOIN webapp.mffoliodetails D ON (A.ororfndamcnatcode = D.foamcnatcode AND A.entityid = D.foentityid) 
                where ororpfuserid = %s AND entityid = %s AND ormffndstatus = 'INCART' AND ormffundordelstrtyp = 'SIP'
            """,(sip_pay_details['mandate_id'],sip_pay_details['mandate_type'],userid,entityid,))
                                
            
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
            
            con.commit()

            #Call lambda to process SIP : START
            #   Don't wait from lambda response here
            #   YET TO IMPLEMENT
            #       fetch eligible SIP records
            #       call prepare order to do validation and prepare json
            #       send only sucess records to bse and store the responses


            #Fetch the SIP RECORDS for getting orderid from BSE: START

            ###  this should be a API call in lambda  #####
            sip_data_for_processing = {
                'userid' : userid,
                'entityid' : entityid,
                'sip_mandate_details': sip_pay_details
            }
            sip_status = mfsiporder.sip_order_processing(sip_data_for_processing)
            ###  this should be a API call in lambda  #####
            
            print(sip_status)
            print("end with SIP")

        #Call lambda to process SIP : END
        if has_ontime_record:
            result.wait()
            print("end with ontime")
            print(result.get())
            pool.close()
            pool.join()
            #con.commit()
            str2=tuple(onetimeorderids)
            print(onetimeorderids)
            print(str2)   
            todt  = datetime.now().strftime('%d-%b-%Y')
            frmdt = (datetime.now() + timedelta(days=-1)).strftime('%d-%b-%Y')            
            
            # No date is sent as orderids are sent in this call
            if screenid == "ordBSEMFbuy":
                mfor_ordertype = "One Time"
            if screenid == "ordBSEMFsell":
                mfor_ordertype = "BSMFsell"

            all_recs = fetchsucfai_recs(con, cur, str2, mfor_ordertype, userid, entityid,frmdt,todt,'VSF')
            resp_recs = all_recs
            #resp_recs = all_recs['one_time']
            resp_recs['has_ontime_rec'] = True
        else:
            resp_recs = {
                'val_success_recs' : [],
                'paypending_recs' : [],
                'failure_recs': [],
                'bse_failure_recs' : [],
                'has_ontime_rec': False
            }

        print(json.dumps(resp_recs))
        db.mydbcloseall(con,cur) 

        return json.dumps(resp_recs)



@app.route('/mforderdetails',methods=['GET','POST','OPTIONS'])
#end point to get the sucess failure records for today
def mforderdetails():
    if request.method=='OPTIONS':
        print ("inside mfordinprogress options")
        return jsonify({'body':'success'})

    elif request.method=='POST':   
        print ("inside mfordinprogress post")
        print(request.headers)
        payload= request.get_json()
        print(payload)
        frmdt = payload['fromdate']
        todt = payload['todate']
        ord_type = payload['order_type']
        rectype = payload['record_type']        

        userid,entityid=jwtnoverify.validatetoken(request)
        
        con,cur=db.mydbopncon()
        #frmdt = datetime.now().strftime('%d/%m/%Y')
        resp_recs = fetchsucfai_recs(con, cur, '%', ord_type, userid, entityid,frmdt,todt,rectype)
        
        cur.close()
        con.close()  
        return jsonify(resp_recs)

def fetchsucfai_recs(con, cur, orid_tuple, ord_type, userid, entityid, fromdt =None, todt=None, rectype = 'ALL' ):
    #Fetch the records with their error message and send it back to front end
    #if no error don't send any record to fronend
    #if error send all the records to front end 
    #-------------------------------- rectype -------------------------------------#
    #  VAS - (O&S) - Sucess records only ie..mfor_orderstatus = 'VAS' (suc_records)
    #  VAF - (O&S) - Failed records only ie..mfor_orderstatus = 'VAF' (fai_records)
    #  VSF - (O&S) - Sucess and Failed records only ie..mfor_orderstatus = 'VAS' & 'VAF' (suc_records & fai_records)
    #  FAI - (O&S) - BSE Failed records only ie..mfor_orderstatus = 'FAI' (bse_fai_records)
    #  SBE - (O)   - Redemption records successfully submitted to BSE
    #  PPY - (O&S) - Pending payme records only ie..mfor_orderstatus = 'PPY'  (pen_pay_records) [for sip this is SIP registration progress record]
    #  BFP - (O&S) - BSE Failed and Pending payme records ie..mfor_orderstatus = 'VAF' & 'FAI' & 'PPY' (fai_records, bse_fai_records & pen_pay_records) [for sip this is SIP registration completed record]
    #  SAS - (S)   - SIP allotment success transaction (equivalent to onetime buy)
    #  SAF - (S)   - SIP allotment Failure transaction (equivalent to onetime FAI)
    #  ALL - (O&S) - All of the above records   (suc_records & fai_records & bse_fai_records & pen_pay_records)     #
    #-------------------------------- rectype -------------------------------------#
    #-------------------------------- ord_type ---------------------------------------------------------#
    #  One Time - Sucess records only ie..mfor_ordertype = 'One Time'
    #  SIP - Failed records only ie..mfor_ordertype = 'SIP'
    #  ALL - Sucess and Failed records only ie..mfor_orderstatus = mfor_ordertype = 'One Time' & 'SIP'
    #-------------------------------- ord_type ----------------------------------------------------------#
    
    if ord_type == 'ALL':
        ord_type = tuple(["One Time","SIP","BSMFsell"])
    elif ord_type == 'One Time' or ord_type == "BSMFsell" or ord_type == "SIP":
        ord_type = tuple([ord_type])

    print("###################")
    print(ord_type)
    print("###################")
    todaysdate = datetime.now().strftime('%d-%b-%Y')
    yestdate = (datetime.now() + timedelta(days=-1)).strftime('%d-%b-%Y')


    if fromdt:
        if todt:
            pass 
        else:
            todt = todaysdate
    else:
        fromdt = yestdate
        todt = todaysdate

    ot_recs = ''
    sip_recs= ''
    print('@@@@@@@@@@@@@@@@@@@fetchsucfai_recs start')
    print(ord_type)
    print(rectype)
    print(orid_tuple)
    for ordtyp in ord_type:
        print(ordtyp)
        if (rectype =='ALL'):
            suc_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'VAS')
            fai_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'VAF')
            bse_fai_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'FAI')
            pen_pay_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'PPY')
            pay_init_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'PPP')
        elif (rectype =='VAS'):
            suc_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'VAS')
            fai_records = ''
            bse_fai_records = ''
            pen_pay_records = ''
            pay_init_records = ''
        elif (rectype =='VAF'):
            suc_records = ''
            fai_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'VAF')
            bse_fai_records = ''
            pen_pay_records = ''
            pay_init_records = ''
        elif (rectype =='VSF'):
            print("inside VSF")
            suc_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'VAS')
            fai_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'VAF')
            bse_fai_records = ''
            pen_pay_records = ''
            pay_init_records = ''
        elif (rectype == 'BFP'):
            print("inside BFP")
            suc_records = ''
            fai_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'VAF')
            bse_fai_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'FAI')
            pen_pay_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'PPY')
            pay_init_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'PPP')
        elif(rectype =='FAI'):
            suc_records = ''
            fai_records = ''
            bse_fai_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'FAI')
            pen_pay_records = ''
            pay_init_records = ''
        elif(rectype =='PPY'):
            suc_records = ''
            fai_records = ''
            bse_fai_records = ''
            pen_pay_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'PPY')
            pay_init_records = one_fetchsucfai_recs(con, cur, orid_tuple, ordtyp, userid, entityid, fromdt, todt, rectype = 'PPP')


        if suc_records == None or suc_records == '':
           suc_records = []
        
        if fai_records == None or fai_records == '':
           fai_records = []

        if bse_fai_records == None or bse_fai_records == '':
           bse_fai_records = [] 

        if pen_pay_records == None or pen_pay_records == '':
           pen_pay_records = []

        if pay_init_records == None or pay_init_records == '':
           pay_init_records = []

        print("before final")
        print(ord_type)
        print(ord_type == "BSMFSELL")
        if "One Time" in ord_type or "BSMFsell" in ord_type:
            print("inside one time")
            print(suc_records)
            print(fai_records)
            print(bse_fai_records)
            print(pen_pay_records)

            ot_recs={
                'val_success_recs': suc_records,
                'failure_recs': fai_records,
                'bse_failure_recs': bse_fai_records,
                'bse_submitted_recs' : '',
                'paypending_recs': pen_pay_records,
                'pay_initiated_recs': pay_init_records
            }
            sip_recs =''
        elif 'SIP' in ordtyp:
            ot_recs = ''
            sip_recs={
                'success_recs': suc_records,
                'failure_recs': fai_records,
                'bse_failure_recs': bse_fai_records,
                'reg_in_prog_recs': pen_pay_records
            }

    resp_recs = {
        'one_time' : ot_recs,
        'sip' : sip_recs
    }
    print(resp_recs)
    print('@@@@@@@@@@@@@@@@@@@fetchsucfai_recs')
    return resp_recs



def one_fetchsucfai_recs(con, cur, orid_tuple, ord_type, userid, entityid, fromdt, todt, rectype):
# Don't call this directly, call this function via fetchsucfai_recs
    qry = "SELECT json_agg(b) FROM ("
    qry = qry + " SELECT X.mfor_uniquereferencenumber,Y.orpfportfolioname,Y.orormffundname,X.mfor_amount,X.mfor_valierrors,X.mfor_clientcode,X.mfor_orderid,"    
    qry = qry + " CASE"
    qry = qry + " WHEN X.mfor_buysell = 'P' THEN 'BUY'" 
    qry = qry + " WHEN X.mfor_buysell = 'R' THEN 'SELL'"
    qry = qry + " END as mfor_buysell,"
    qry = qry + " X.mfor_qty, X.mfor_producttype"
    qry = qry + " FROM webapp.mforderdetails X"
    qry = qry + " LEFT OUTER JOIN webapp.pfmforlist Y ON (Y.ororportfolioid = X.mfor_ororportfolioid AND Y.orormfpflistid = X.mfor_orormfpflistid AND Y.entityid = X.mfor_entityid)"        
    qry = qry + " WHERE mfor_ordertype = %s"

    if orid_tuple == '%':
        qry = qry + " AND mfor_uniquereferencenumber like %s"
    elif orid_tuple:
        qry = qry + " AND mfor_uniquereferencenumber in %s"

    
    qry = qry + " AND mfor_orderstatus = %s"
    qry = qry + " AND mfor_pfuserid = %s AND mfor_entityid =%s"
    qry = qry + " AND date(mfor_orderoctime) BETWEEN %s AND %s"
    qry = qry + " ORDER BY Y.orpfportfolioname,Y.orormffundname"
    qry = qry + " ) AS b;"
    
    if orid_tuple:
        command = cur.mogrify(qry,(ord_type,orid_tuple,rectype,userid,entityid,fromdt,todt,))
    else:
        command = cur.mogrify(qry,(ord_type,rectype,userid,entityid,fromdt,todt,))

    print(command)
    cur, dbqerr = db.mydbfunc(con,cur,command)
                            
    if cur.closed == True:
        if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
            dbqerr['statusdetails']="Validation records fetch failed"
        resp = make_response(jsonify(dbqerr), 400)
        return(resp)
    print("Line 1070: total records",cur.rowcount)
    
    #Model to follow in all fetch
    records=[]
    for record in cur:
        #print(record)
        records = record[0]
    #print("iam printing records to see")(self, parameter_list):
    
    return records

#This is when orders are sent to BSE
@app.route('/mfordersubmit',methods=['GET','POST','OPTIONS'])
#example for model code http://www.postgresqltutorial.com/postgresql-python/transaction/
def mfordersubmit():
    if request.method=='OPTIONS':
        print ("inside mfordersubmit options")
        return jsonify({'body':'success'})

    elif request.method=='POST':   
        print ("inside mfordersubmit post")

        print(request.headers)
 
        payload_org= request.get_json()
        #payload = request.stream.read().decode('utf8')    
        print(payload_org)

        one_time_pay_details = payload_org['one_time_pay']
        sip_pay_details = payload_org['sip_pay']  #Not required for one time
        payload = payload_org['succrecs']
        userid = payload_org['userid']
        entityid = payload_org['entityid']


        ord_ids=[]
        for payld in payload:
            ord_ids.append(payld['mfor_uniquereferencenumber'])

        str=tuple(ord_ids)
        print(str)

        if userid is None or userid == '':
            userid,entityid=jwtnoverify.validatetoken(request)
        
        if entityid is None or entityid == '':
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
        
        ###  this should be a API call in lambda  #####
        orderresp = mforderapi.place_order_bse(order_records)
        ###  this should be a API call in lambda  #####

        print(orderresp)
        #Add code to update the order id

        fndstatus= 'COMPF'
        savetimestamp = datetime.now()
        pfsavetimestamp=savetimestamp.strftime('%Y-%m-%d %H:%M:%S')
        segment = 'BSEMF'

        ot_orderids=[]
        sip_orderids=[]



        for orderres in orderresp:

            command = cur.mogrify("BEGIN;")
            cur, dbqerr = db.mydbfunc(con,cur,command)
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="DB query failed, BEGIN failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)

            if orderres['success_flag'] == '0':
                
                if orderres['order_type'] == 'OneTime':
                    orderstatus = "PPY"
                    ot_orderids.append(orderres['trans_no'])
                elif orderres['order_type'] == 'BSMFsell':
                    orderstatus = "SBE"
                    ot_orderids.append(orderres['trans_no'])
                elif orderres['order_type'] == 'SIP':
                    orderstatus = "SRS"
                    sip_orderids.append(orderres['trans_no'])                   
                    
                    command = cur.mogrify("""
                        UPDATE webapp.mforderdetails SET mfor_orderstatus = %s, mfor_orderid = %s, mfor_bseremarks = %s WHERE mfor_uniquereferencenumber = %s AND mfor_pfuserid = %s AND mfor_entityid = %s;
                    """,(orderstatus, orderres['order_id'],orderres['bse_remarks'],orderres['trans_no'],userid,entityid,))

            else:
                
                if orderres['order_type'] == 'OneTime':
                    orderstatus = "FAI"
                    ot_orderids.append(orderres['trans_no'])
                elif orderres['order_type'] == 'BSMFsell':
                    orderstatus = "FAI"
                    ot_orderids.append(orderres['trans_no'])
                elif orderres['order_type'] == 'SIP':
                    orderstatus = "FAI"
                    sip_orderids.append(orderres['trans_no'])                   
                
                command = cur.mogrify("""
                        UPDATE webapp.mforderdetails SET mfor_orderstatus = %s, mfor_valierrors = %s WHERE mfor_uniquereferencenumber = %s AND mfor_pfuserid = %s AND mfor_entityid = %s;
                """,(orderstatus,orderres['bse_remarks'],orderres['trans_no'],userid,entityid,))

            print(command)
            cur, dbqerr = db.mydbfunc(con,cur,command)

            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="selecting order to submit to BSE failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            '''
                elif orderres['order_type'] == 'SIP':
                    
                    command = cur.mogrify("""
                        UPDATE webapp.mforderdetails SET mfor_orderstatus = %s, mfor_orderid = %s, mfor_bseremarks = %s WHERE mfor_uniquereferencenumber = %s AND mfor_pfuserid = %s AND mfor_entityid = %s;
                    """,(orderres['order_id'],orderres['bse_remarks'],orderres['trans_no'],userid,entityid,))
                    print(command)
                    cur, dbqerr = db.mydbfunc(con,cur,command)
                    if cur.closed == True:
                        if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                            dbqerr['statusdetails']="selecting order to submit to BSE failed"
                        resp = make_response(jsonify(dbqerr), 400)
                        return(resp)
            
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
                if cur.closed == True:
                    if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                        dbqerr['statusdetails']="selecting order to submit to BSE failed"
                    resp = make_response(jsonify(dbqerr), 400)
                    return(resp)
            '''
            command = cur.mogrify(
                """
                UPDATE webapp.pfmforlist SET ormffndstatus = %s, ormflmtime = %s 
                WHERE ormffndstatus in ('SUBM') 
                AND orormfpflistid = (SELECT mfor_orormfpflistid FROM webapp.mforderdetails WHERE mfor_uniquereferencenumber = %s AND mfor_producttype = %s AND mfor_pfuserid = %s AND mfor_entityid = %s)                    
                AND orormfprodtype = %s AND ororpfuserid = %s AND entityid = %s;
                """,(fndstatus,pfsavetimestamp,orderres['trans_no'],segment,userid,entityid,segment,userid,entityid,))

            print(command)
            cur, dbqerr = db.mydbfunc(con,cur,command)
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="selecting order to submit to BSE failed"
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)

            con.commit()

        #if orderres['order_type'] == 'OneTime':
        if len(ot_orderids) > 0:
            if orderres['order_type'] == 'OneTime':
                ordtyp = "One Time"
            elif orderres['order_type'] == 'BSMFsell':
                ordtyp = "BSMFsell"

            str2 = tuple(ot_orderids)
            
            frmdt = (datetime.now() + timedelta(days=-1)).strftime('%d-%b-%Y')
            todt = datetime.now().strftime('%d-%b-%Y')

            all_recs = fetchsucfai_recs(con, cur, str2, ordtyp , userid, entityid, frmdt, todt, 'BFP')
            print('*******************ord_type')
            print(orderres['order_type'])
            print(str2)
            print(all_recs)
            print('*******************ord_type')

            resp_recs = all_recs

            print(json.dumps(resp_recs))
      
        #elif orderres['order_type'] == 'SIP':
        elif len(sip_orderids) > 0:
            resp_recs = {
                'status' : 'completed',
                'sip_orderids': sip_orderids
                }
            print(json.dumps(resp_recs))

        db.mydbcloseall(con,cur)
        return json.dumps(resp_recs)


@app.route('/mforderpayment',methods=['GET','POST','OPTIONS'])
def mforderpayment():
    if request.method=='OPTIONS':
        print ("inside mforderpayment options")
        return jsonify({'body':'success'})

    elif request.method=='POST':   
        print ("inside mforderpayment post")

        print(request.headers)
        payload_org= request.get_json()
        #payload = request.stream.read().decode('utf8')    
        print(payload_org)
        
        userid,entityid=jwtnoverify.validatetoken(request)
        savetimestamp = datetime.now()
        #pfsavedate=savetimestamp.strftime('%Y%m%d') 
        pfsavetimestamp=savetimestamp.strftime('%Y/%m/%d %H:%M:%S')
        print(pfsavetimestamp)

        one_time_pay_details = payload_org['one_time_pay']
        #sip_pay_details = payload_org['sip_pay']  #Not required for one time
        payload = payload_org['succrecs']

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
            'total_amt': total_amt,
            'acc_num': one_time_pay_details['acnum'],
            'bank_id': one_time_pay_details['bank_id'],
            'ifsc': one_time_pay_details['ifsc'],
            'logout_url': webapp_settings.LOGOUTURL_BANKLNK[webapp_settings.LIVE],
            'mode': one_time_pay_details['mode'],
            'mandate_id':''
        }


        print('record_to_submit')
        print(record_to_submit)

        str2=tuple(ord_ids)
        print(ord_ids)
        print("line:1276",str2)   

        con,cur=db.mydbopncon()

        command = cur.mogrify("""
                    UPDATE webapp.mforderdetails SET mfor_orderstatus = 'PPP', mfor_orderlmtime  = %s WHERE mfor_orderid IN %s AND mfor_pfuserid = %s AND mfor_entityid = %s;
                    """,(pfsavetimestamp,str2,userid,entityid,))
        print("line:1282",command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="selecting order to submit to BSE failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)

        fndstatus = 'PAYPR'
        segment = 'BSEMF'
        command = cur.mogrify(
        """
        UPDATE webapp.pfmforlist SET ormffndstatus = %s, ormflmtime = %s 
        WHERE ormffndstatus in ('SUBM') 
        AND orormfpflistid = (SELECT mfor_orormfpflistid FROM webapp.mforderdetails WHERE mfor_orderid IN %s AND mfor_producttype = %s AND mfor_pfuserid = %s AND mfor_entityid = %s)                    
        AND orormfprodtype = %s AND ororpfuserid = %s AND entityid = %s;
        """,(fndstatus,pfsavetimestamp,str2,segment,userid,entityid,segment,userid,entityid,))

        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                dbqerr['statusdetails']="selecting order to submit to BSE failed"
            resp = make_response(jsonify(dbqerr), 400)
            return(resp)        

        con.commit()                                
        # FOR DIRECT PAYMENT LINK
        url_pay=mforderapi.get_payment_link_direct(record_to_submit)
        print('url_pay')
        print(url_pay)

        if (url_pay['status']=='failed'):
            # FOR BSE PAYMENT LINK
            record_to_submit['logout_url']= webapp_settings.LOGOUTURL_BSELNK[webapp_settings.LIVE]
            url_pay = None
            url_pay = mforderapi.get_payment_link_bse(record_to_submit)
            #Code to be re-written to include http call
                
    return jsonify(url_pay)
  

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
    print("processing order " + ord['mfor_uniquereferencenumber'] + " ordrtype is " + ord['mfor_ordertype'])
    #time.sleep(0.5)
    #return json.dumps({'mfor_uniquereferencenumber': ord['mfor_uniquereferencenumber'],'order_id': '','amount':ord['mfor_amount']})
    
    if(ord['mfor_ordertype'] == "One Time" or ord['mfor_ordertype'] == "BSMFsell"):
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
        if ord['mfor_sipmandatetype'] == 'I':
            has_error, order_json = prepare_isip_ord(ord)
        elif ord['mfor_sipmandatetype'] == 'X':
            #has_error, order_json = prepare_xsip_ord(ord)
            pass
        elif ord['mfor_sipmandatetype'] == 'E':
            #has_error, order_json = prepare_esip_ord(ord)
            pass

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

    db.mydbcloseall(con,cur)

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
        'mfor_ordertype': "OneTime" if ord['mfor_ordertype'] == "One Time" else ord['mfor_ordertype']
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
    con1, cur1 = db.mydbopncon()

    if (ord['mfor_buysell'] == 'P'):        
        # PURCHASE transaction        
        data_dict['buy_sell'] = 'P'
        data_dict['order_id'] = ''

        
        if(ord['mfor_amount']):
            if (ord['mfor_amount'] <= 0 ):
                haserror = True
                errormsg = errormsg + "ORDER amount is zero or negative: " 
            else:
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
        data_dict['buy_sell'] = 'R'
        data_dict['order_id'] = ''
        data_dict['order_amt'] = 0
        
        if(ord['mfor_qty']):
            if (ord['mfor_qty'] <= 0 ):
                haserror = True
                errormsg = errormsg + "Redemption qty is zero or negative: " 
            else:
                
                if haserror:
                    pass
                else:
                    haserror, errormsg = validate_add_details_to_order("order_qty", ord, con1, cur1)
                    if haserror:
                        pass
                    else:
                        data_dict['order_qty'] = ord['mfor_qty']
                        data_dict['all_redeem'] = ord['mfor_allredeem']
                        data_dict['min_redeem'] = ord['mfor_minredemption']
        else:
            haserror = True
            errormsg = errormsg + "Missing ORDER Quantity: " 
        
        haserror, errormsg = haserror, errormsg if haserror else validate_add_details_to_order("foliono", ord, con1, cur1)
        if haserror:
            errormsg = errormsg + "error in locating foliono: " 
        else:
            data_dict['folio_no'] = ord['mfor_foliono']

        data_dict['remarks'] = ''

        haserror, errormsg = haserror, errormsg if haserror else validate_add_details_to_order("fresh_addi", ord, con1, cur1)
        if haserror:
            errormsg = errormsg + "error in ariving fresh or additional purchase: " 
        else:
            data_dict['buy_sell_type'] = ord['mfor_buyselltype']

    print('####################')
    print(data_dict)
    print('####################')
    print(haserror)
    if cur1.closed == False:
        db.mydbcloseall(con1,cur1)

    if haserror:
        return (True , errormsg)
    else:
        return( False, json.dumps(data_dict))

# Function to validate redemption order quantiy against holding quantity
def validate_add_details_to_order(fld_to_val, ord, con1, cur1):
    #Validate order qty
    haserror = False
    errormsg = None
    buy_sell = ord['mfor_buysell']
    entity = ord['mfor_entityid']
    usrid = ord['mfor_pfuserid']
    pfid = ord['mfor_ororportfolioid']
    prodtyp = ord['mfor_producttype']
    schmcd = ord['mfor_schemecd']

    command = cur1.mogrify("""
        SELECT row_to_json(a) from (
        select COALESCE(dp.dpos_unit - (dp.dpos_unit_blocked + dp.dpos_unit_utilised),0) available_unit,COALESCE(fndminredamt,0) fndminredamt,
        COALESCE(fndmulredamt,0) fndmulredamt, COALESCE(fo.fopfamcfolionumber,'') foliono,
        CASE 
            WHEN 
                ((SELECT COUNT(1) WHERE dpos_entityid = %s AND dpos_pfuserid = %s  AND dpos_pfportfolioid = %s AND dpos_producttype = %s AND dpos_schemecd = %s) > 0) 
                    THEN 'ADDITIONAL' 
                    ELSE 'FRESH'            
        END AS buyselltyp
        from webapp.dailyposition dp
        LEFT JOIN webapp.fundmaster fm ON fm.fndschcdfrmbse = dp.dpos_schemecd AND fm.entityid = dp.dpos_entityid
        LEFT JOIN webapp.mffoliodetails fo ON fo.foentityid = dp.dpos_entityid AND fo.fopfportfolioid = dp.dpos_pfportfolioid AND fo.foamcnatcode = fm.fndamcnatcode
        WHERE dpos_entityid = %s AND dpos_pfuserid = %s  AND dpos_pfportfolioid = %s AND dpos_producttype = %s AND dpos_schemecd = %s) as a
    """,(entity,usrid,pfid,prodtyp,schmcd,entity,usrid,pfid,prodtyp,schmcd,))

    cur1, dbqerr = db.mydbfunc(con1,cur1,command)

    if cur1.closed == True:
        if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
            haserror = True
            errormsg = "order data fetch failed with DB error"
            print(haserror,errormsg)

    if cur1.rowcount > 1:
        haserror = True
        errormsg = "order data fetch returned more rows"
        print(haserror,errormsg)

    if cur1.rowcount == 1:
        record = cur1.fetchall()[0][0]
        print("print success records")
        print(record)

    if haserror:
        pass
    else:
        if fld_to_val == "order_qty":        
            if buy_sell == "R":
                if record['available_unit'] <= ord['mfor_qty']:
                    haserror = True
                    ms = "Order quantity is more than avaialble quantity"
                    errormsg = ms if errormsg == None else errormsg  + " | " + ms

                if (ord['mfor_qty'] % record['fndmulredamt'] > 0):
                    haserror = True
                    ms = "redumption qty not in allowed multiples (" +  record['fndmulredamt'] + ")"
                    errormsg = ms if errormsg == None else errormsg  + " | " + ms
                
                if (ord['mfor_qty'] < record['fndminredamt'] > 0):
                    haserror = True
                    ms = "redumption qty is less than min redemption allowed (orderqty: " + ord['mfor_qty'] + ", min redemption allowed: " + record['fndminredamt'] + ")"
                    errormsg = ms if errormsg == None else errormsg  + " | " + ms

                if haserror:
                    pass
                else:
                    # Dont change ord['mfor_qty'] it is validated and perfect
                    ord['mfor_allredeem'] = "Y" if record['available_unit'] == ord['mfor_qty'] else "N"
                    ord['mfor_minredemption'] = "Y" if record['fndminredamt'] == ord['mfor_qty'] else "N"

        if fld_to_val == "foliono":
            if buy_sell == "R":
                # incase this portfolio has more foliono for the same fund the order to be split
                # future work
                ord['mfor_foliono'] = record['foliono'] if ord['mfor_foliono'] == '' or ord['mfor_foliono'] == None else ord['mfor_foliono']
        
        if fld_to_val == "fresh_addi":
            ord['mfor_buyselltype'] = record['buyselltyp']

        if haserror:
            pass
        else:
            # Update the DB with the arrived values
            qry_str = "UPDATE webapp.mforderdetails SET mfor_buyselltype = %s, mfor_foliono = %s"

            if buy_sell == "R":
                qry_str = qry_str + ", mfor_allredeem = %s, mfor_minredemption = %s"

            qry_str = qry_str + " WHERE mfor_entityid = %s AND mfor_pfuserid = %s AND mfor_ororportfolioid = %s AND mfor_producttype = %s AND  mfor_schemecd = %s AND ormffndstatus = 'INCART' AND mfor_ordertype = %s;"

            if buy_sell == "R":
                command = cur1.mogrify(qry_str,(ord['mfor_buyselltype'], ord['mfor_foliono'], ord['mfor_allredeem'], ord['mfor_minredemption'],entity,usrid,pfid,prodtyp,schmcd,ord['mfor_ordertype']))
            else:
                command = cur1.mogrify(qry_str,(ord['mfor_buyselltype'], ord['mfor_foliono'],entity,usrid,pfid,prodtyp,schmcd,ord['mfor_ordertype']))
                
            
            print(command)
            cur1, dbqerr = db.mydbfunc(con1,cur1,command)

            if cur1.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    haserror = True
                    ms = "order data additional data update failed with DB error"
                    errormsg = ms if errormsg == None else errormsg  + " | " + ms
                    print(haserror,errormsg)
            else:
                con1.commit()
        # Update the DB with the arrived values end
    # command 
    # return values: rqty, rall, rmin,  err, failreason
    return haserror, errormsg

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
        'dpc_flg' : 'N',
        'xsip_reg_id' : '',        
        'Param3' : '',
        'xsip_mandate_id': '',
        #The below 2 recs should be deleted in API before sending to BSE.
        'mfor_ordertype': 'SIP',
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


    #for testing lines
    #ord['mfor_sipmandateid'] = 'BSE000000016247'
    #for testing lines
    '''
    if (ord['mfor_sipmandatetype'] == 'XSIP'):
        data_dict['isip_mandate_id'] = ''
        if(ord['mfor_sipmandateid']):
            data_dict['xsip_mandate_id'] = ord['mfor_sipmandateid']            
        else:
            haserror = True
            errormsg = errormsg + "Missing XSIP Mandate id: " 


    if (ord['mfor_sipmandatetype'] == 'ESIP'):
        data_dict['xsip_mandate_id'] = ''
        if(ord['mfor_sipmandateid']):
            data_dict['isip_mandate_id'] = ord['mfor_sipmandateid']
        else:
            haserror = True
            errormsg = errormsg + "Missing ESIP Mandate id: " 
    '''

    if(ord['mfor_sipmandateid']):
        data_dict['isip_mandate_id'] = ord['mfor_sipmandateid']
    else:
        haserror = True
        errormsg = errormsg + "Missing ISIP Mandate id: " 

    if(ord['mfor_sipmandatetype']):
        data_dict['mfor_sipmandatetype'] = ord['mfor_sipmandatetype']
    else:
        haserror = True
        errormsg = errormsg + "Missing SIP Mandate type: " 


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
        print('11111111111111111111111111111111')
        bse_order = 'nat'
        print('11111111111111111111111111111111')
        #bse_order = json.loads(payload)
        print(bse_order)
        #return bse_order
        return redirect("http://localhost:4200/paycomp/no", code=302)  


@app.route('/mfordpaystatus',methods=['GET','POST','OPTIONS'])
def mfordpaystatus():
    if request.method=='OPTIONS':
        print ("inside mfordpaystatus options")
        return 'inside mfordpaystatus options'

    elif request.method=='POST' :
        print("inside mfordpaystatus POST")
        print((request))        
        userid,entityid=jwtnoverify.validatetoken(request)
        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        con,cur=db.mydbopncon()
        
        print(con)
        print(cur)
        
        command = cur.mogrify(
            """
            SELECT row_to_json(art) FROM (SELECT mfor_producttype,mfor_orderid,mfor_clientcode FROM webapp.mforderdetails WHERE mfor_orderstatus IN ('PPP','PAW') AND mfor_pfuserid = %s AND mfor_entityid = %s) art;
            """,(userid,entityid,))
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
        print(records)

        order_recs = []
        for record in records:
            order_rec = {
                'client_code':record['mfor_clientcode'],
                'order_id': record['mfor_orderid'],
                'segment' : record['mfor_producttype']
            }
            order_recs.append(order_rec)
        
        print(order_recs)
        #shuld be call api and return response.  Processing done in background
        submit_recs_status = bg.mfordpaystatusbg(order_recs,userid,entityid)
        print(submit_recs_status)
        #shuld be call api and return response.  Processing done in background
                               
        cur.close()
        con.close()    
        print("payment status done")
        return jsonify({'body':'payment status done'})
        #return redirect("http://localhost:4200/securedpg/dashboard", code=301)  

@app.route('/orderhistfetch',methods=['GET','POST','OPTIONS'])
def mforderhist():
    if request.method=='OPTIONS':
        print ("inside orderapi options")
        return 'inside orderapi options'

    elif request.method=='POST' :
        print("inside orderapi POST")

        print((request))        
        #userid,entityid=jwtnoverify.validatetoken(request)
        print(datetime.now().strftime('%d-%m-%Y %H:%M:%S'))
        payload= request.get_json()
        #payload=json.loads(payload)
        print(payload)

        freq = payload.get('freq',None)
        # pageiden = sum (daily + weekly + monthly).
        # pageiden = range (for start and end date sent by client).
        product = payload.get('product',None)

        print(freq)
        print(product)
        
        #request_status_all = []
        #failure_reason_all = None
        today_order = None
        weeks_order = None
        months_order = None
        daterange = None
        failure_reason = None
        request_status = None

        if product == None:
            request_status = "datafail"
            failure_reason = "product is sent as blank by client"     
        elif product == "Mutual Fund":
            product = 'BSEMF'
        elif product == "Stocks":
            product = 'EQ'
        
        print(product)

        userid,entityid=jwtnoverify.validatetoken(request)


        
        if freq == 'today':
            print("inside today")
            # Today's order details
            today = datetime.now().date()
            startday = today
            endday = today            
            print(startday)
            print(endday)
            today_order,request_status, failure_reason = get_order_history(userid,entityid,product,startday.strftime('%d-%b-%Y'),endday.strftime('%d-%b-%Y'))
            #today_order,request_status, failure_reason = 'today',None, None
            
            '''
            if request_status:
                request_status_all.append (request_status)
            failure_reason_all = (failure_reason_all +  ' | ' + failure_reason) if failure_reason_all else failure_reason
            '''
        elif freq == 'week':
            print("inside week")
            # Weeks's order details excluding today's
            today = datetime.now().date()
            startday = today - timedelta(days=today.weekday())
            endday = startday + timedelta(days=6)         
            print(startday)
            print(endday)
            weeks_order,request_status, failure_reason = get_order_history(userid,entityid,product,startday.strftime('%d-%b-%Y'),endday.strftime('%d-%b-%Y'))
            
            '''
            if request_status:
                request_status_all.append (request_status)
            failure_reason_all = (failure_reason_all +  ' | ' + failure_reason) if failure_reason else failure_reason
            '''
        elif freq == 'month':
            print("inside month")
            # Month's order details excluding today's & weeks
            today = datetime.now().date()
            startday = datetime(today.year, today.month, 1)
            endday = datetime(today.year, today.month, calendar.mdays[datetime.today().month])
            print(startday)
            print(endday)
            #startday = (datetime.now() + timedelta(days=8)).strftime('%d-%b-%Y')
            #endday = (datetime(date.year, date.month, calendar.mdays[date.month])).strftime('%d-%b-%Y')
            months_order,request_status, failure_reason = get_order_history(userid,entityid,product,startday.strftime('%d-%b-%Y'),endday.strftime('%d-%b-%Y'))
            
            '''
            if request_status:
                request_status_all.append (request_status)
            failure_reason_all = (failure_reason_all +  ' | ' + failure_reason) if failure_reason else failure_reason
            '''
        elif freq == 'adhoc':
            print("inside adhoc")
            startday = payload.get('startdt',None)
            endday = payload.get('enddt',None)
            startday = datetime.strptime(startday,'%Y-%m-%d') if startday else startday
            endday = datetime.strptime(endday,'%Y-%m-%d') if endday else endday

            if startday == None or endday == None:
                request_status = "datafail"
                failure_reason = "Start date and End date missing in the request"
            elif (abs(startday - endday).days) > 90:
                request_status = "datafail"
                failure_reason = "Date range canot exceed 3 months"            
            else:            
                daterange,request_status, failure_reason = get_order_history(userid,entityid,product,startday.strftime('%d-%b-%Y'),endday.strftime('%d-%b-%Y'))                
        else:
            pass

        '''
        if request_status:
            request_status_all.append (request_status)

        failure_reason_all = (failure_reason_all +  ' | ' + failure_reason) if failure_reason_all else failure_reason
        '''

        print(failure_reason)
        # Check for DB error and send user friendly error msg to front end
        
        '''
        if "dbfail" in request_status_all or "datafail" in request_status_all:
            req_status = "failed"
        '''
        order_data = {
            'todaydata'  :     [] if today_order == None else today_order,
            'weekdata'   :     [] if weeks_order == None else weeks_order,
            'monthdata'  :     [] if months_order == None else months_order,
            'daterange'  :     [] if daterange == None else daterange,
            'status'     :     'success' if request_status == None else request_status,
            'failreason' :     '' if failure_reason == None else failure_reason
        }

        time.sleep(1)
        print("order history data records:")
        print(order_data)

        
        if order_data['status'] == "success":
            return make_response(jsonify(order_data), 200)
        else:
            return make_response(jsonify(order_data), 400)



def get_order_history(userid,entityid,product,fromdt,todt,offset = 0):
    con,cur=db.mydbopncon()    
    print(con)
    print(cur)
    record = None
    status = None 
    failreason = None
    command = cur.mogrify(
        """
        SELECT json_agg(b) FROM (
            SELECT
                tran_orderdate AS trandate,
                tran_schemecd AS schemecode,
                fndmas.fnddisplayname as schemename,
                tran_producttype AS prodtyp,
                CASE
                    WHEN tran_producttype = 'BSEMF' THEN 'MUTUAL FUNDS'
                    WHEN tran_producttype = 'SGB' THEN 'SGB'
                    WHEN tran_producttype = 'EQ' THEN 'Equity'
                    WHEN tran_producttype = 'HEQ' THEN 'Home Equity'
                END AS product,
                tran_pfportfolioid AS pfid, tran_unit AS units, tran_nav AS trannav, tran_invamount AS invamt,
                (
                    SELECT fndnav.navc_value curnav
                    FROM webapp.navcurload fndnav
                    WHERE fndnav.navc_date = (SELECT MAX(A.navc_date) FROM webapp.navcurload A WHERE A.navc_schmcdbse = tran.tran_schemecd)
                    AND fndnav.navc_schmcdbse = tran.tran_schemecd
                ) AS curnav                        
            FROM webapp.trandetails tran
            LEFT JOIN webapp.fundmaster fndmas ON fndmas.fndschcdfrmbse = tran_schemecd 
            WHERE tran_producttype = %s AND tran_entityid = %s AND tran_pfuserid = %s
            AND tran_orderdate BETWEEN %s AND %s
            ORDER BY tran_orderdate,tran_schemecd,tran_producttype,tran_pfportfolioid
            OFFSET %s
        ) b;
        """,(product, entityid, userid, fromdt, todt, offset,))	
    print(command)
    cur, dbqerr = db.mydbfunc(con,cur,command)

    if cur.closed == True:
        if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
            status = "dbfail"
            failreason = "pf product wise fetch failed with DB error"
            print(status,failreason)
    #print(cur.fetchall())
    print(cur.rowcount)
    if cur.rowcount > 1:
        status = "dbfail"
        failreason = "pf product wise fetch returned more rows"
        print(status,failreason)

    if cur.rowcount == 1:
        record = cur.fetchall()[0][0]
        print(record)
          
    cur.close()
    con.close()    
    
    return record, status, failreason

@app.route('/ordplacedetails',methods=['GET','POST','OPTIONS'])
#end point to get the sucess failure records for today
def ordplacedetails():
    if request.method=='OPTIONS':
        print ("inside mfordinprogress options")
        return jsonify({'body':'success'})

    elif request.method=='POST':   
        print ("inside mfordinprogress post")
        print(request.headers)
        payload= request.get_json()
        print(payload)
        product = payload.get('prod', None)        #BSEMF,EQ,IN
        trantype = payload.get('trantype', None)   #sell, buy, stp
        pfid = payload.get('pfid', None)   #sell, buy, stp


        userid,entityid=jwtnoverify.validatetoken(request)
        status = None
        failreason = None

        if product == None:
            status = "datafail"
            if failreason:
                failreason = failreason + "product details not sent by client|"
            else:
                failreason = "product details not sent by client|"
        elif trantype == None:
            status = "datafail"
            if failreason:
                failreason = failreason + "No details on the product provided by client|"
            else:
                failreason = "No details on the product provided by client|"
        elif pfid == None or pfid == '':
            status = "datafail"
            if failreason:
                failreason = failreason + "No details on the product provided by client|"
            else:
                failreason = "No details on the product provided by client|"

        if status == None:
            if product+trantype == 'BSEMFsell':
                placeorderrec,request_status,failure_reason = get_order_details(userid,entityid,product,trantype,pfid)


        # Check for DB error and send user friendly error msg to front end
        if request_status == "dbfail":
            request_status = "failed"
            failure_reason = "Chart Data base Error contact Adminstrator"
        elif request_status == "datafail":
            request_status = "failed"
            failure_reason = "Chart Data Error contact Adminstrator"
        
        placeorderrec['status']  = 'success'

        if placeorderrec['status'] == "success":
            return make_response(jsonify(placeorderrec), 200)
        else:
            return make_response(jsonify(placeorderrec), 400)

def get_order_details(userid,entityid,product,trantype,pfid):
    record = None
    status = None
    failreason = None
    con,cur=db.mydbopncon()

    if( (product + trantype) == 'BSEMFsell'):
        whattran = 'R'
        fndflowstatus = 'INCART'

    if (pfid == None):
        pfid = "%"
    
    print(con)
    print(cur)
    
    #cur.execute("select row_to_json(art) from (select a.*, (select json_agg(b) from (select * from pfstklist where pfportfolioid = a.pfportfolioid ) as b) as pfstklist, (select json_agg(c) from (select * from pfmflist where pfportfolioid = a.pfportfolioid ) as c) as pfmflist from pfmaindetail as a where pfuserid =%s ) art",(userid,))
    #command = cur.mogrify("select row_to_json(art) from (select a.*,(select json_agg(b) from (select * from webapp.pfstklist where pfportfolioid = a.pfportfolioid ) as b) as pfstklist, (select json_agg(c) from (select c.*,(select json_agg(d) from (select * from webapp.pfmforlist where orormflistid = c.ormflistid AND ormffndstatus='INCART' AND entityid=%s) as d) as ormffundorderlists from webapp.pfmflist c where orportfolioid = a.pfportfolioid ) as c) as pfmflist from webapp.pfmaindetail as a where pfuserid =%s AND entityid=%s) art",(entityid,userid,entityid,))
    command = cur.mogrify(
    """
    WITH portport as (SELECT dpos_pfportfolioid, dpos_schemecd, dpos_producttype FROM webapp.dailyposition WHERE dpos_producttype = %s AND dpos_entityid = %s AND dpos_pfuserid = %s AND dpos_pfportfolioid = %s) 				
    SELECT json_agg(art) FROM (
            (SELECT ls.*,
                (SELECT row_to_json(dpv.*) FROM webapp.dailyposition dpv WHERE dpv.dpos_pfportfolioid =  ls.orportfolioid  AND dpv.dpos_schemecd = ls.ormffndcode ) as dailyposition,
                (SELECT json_agg(d) FROM 
                    (
                    with s as
                        (SELECT orl.*,
                        case when COALESCE(orl.ormffundordunit,0)>0 THEN 'true'::boolean ELSE 'false'::boolean END orderselect
                        FROM webapp.pfmforlist orl WHERE orl.orormflistid = ls.ormflistid 
                        AND orl.orormfprodtype = %s AND orormfwhattran = %s AND ormffndstatus = %s)
                    select s.*,
                    case when COALESCE(s.ormffundordunit,0)>0 THEN 'true'::boolean ELSE 'false'::boolean END orderselect, 
                    COALESCE(s.ormffundordunit,0) ormffundordunit, COALESCE(s.entityid,ls.entityid) entityid, COALESCE(s.orormffndcode,ls.ormffndcode) orormffndcode, COALESCE(s.orormffundname,ls.ormffundname) orormffundname,
                    COALESCE(s.orormfprodtype,ls.ormfprodtype) orormfprodtype, COALESCE(s.orormfwhattran,%s) orormfwhattran, COALESCE(s.ororpfuserid,ls.orpfuserid) ororpfuserid,
                    COALESCE(s.ororportfolioid,ls.orportfolioid) ororportfolioid, COALESCE(s.orormflistid,ls.ormflistid) orormflistid,
                    COALESCE(s.orormffndcode,ls.ormffndcode) orormffndcode, COALESCE(s.orormftrantype,'NEW') orormftrantype,
                    COALESCE(s.ormffndstatus,%s) ormffndstatus, COALESCE(s.ormffundordelstrtyp,'BSMFsell') ormffundordelstrtyp,
                    COALESCE(s.ormffundordelsstdt,'0') ormffundordelsstdt, COALESCE(s.ormffundordelsfreq,'0') ormffundordelsfreq,
                    COALESCE(s.ormffundordelsamt,0) ormffundordelsamt, COALESCE(s.ormfsipinstal,0) ormfsipinstal
                    from (select 1 as x) x 
                    left join s on x.x = 1
                    )
                as d) as ormffundorderlists 
            FROM webapp.pfmflist ls where ls.orportfolioid in (SELECT distinct dpos_pfportfolioid FROM portport) 
            AND ls.ormffndcode in (SELECT distinct dpos_schemecd FROM portport WHERE dpos_pfportfolioid = ls.orportfolioid) 
            AND ls.ormfprodtype = %s 
            AND ls.orpfuserid = %s AND ls.entityid = %s
            ) 
    ) art;
    """,(product,entityid,userid,pfid,product,whattran,fndflowstatus,whattran,fndflowstatus,product,userid,entityid,))


    '''
    QUERY WITH DATA TO RUN FOR CHECKS
    WITH portport as (select dpos_pfportfolioid, dpos_schemecd, dpos_producttype from webapp.dailyposition where dpos_producttype = 'BSEMF' AND dpos_entityid = 'IN' AND dpos_pfuserid =  '0YzmOxwmwjZM1i7ZCLY5hLfn7SG3') 				
    select row_to_json(art) from (

                                            (select ls.*,
                                                (select row_to_json(dpv.*) from webapp.dailyposition dpv where dpv.dpos_pfportfolioid  = ls.orportfolioid  AND dpv.dpos_schemecd = ls.ormffndcode ) as dailyposition,												 	
                                                (select json_agg(d) from 
                                                    (
                                                    with s as
                                                (select orl.*
                                                        from webapp.pfmforlist orl 
                                                        where orl.orormflistid = ls.ormflistid 
                                                        AND orl.orormfprodtype = 'BSEMF' AND orormfwhattran = 'R' AND ormffndstatus = 'INCART') 
                                                        select s.*, 
                                                                case when COALESCE(s.ormffundordelsamt,0)>0 THEN 'true'::boolean ELSE 'false'::boolean END orderselect,
                                                                COALESCE(s.ormffundordunit,0) ormffundordunit,
                                                                COALESCE(s.entityid,ls.entityid) entityid,
                                                                COALESCE(s.orormffndcode,ls.ormffndcode) orormffndcode, COALESCE(s.orormftrantype,'N') orormftrantype,
                                                                COALESCE(s.ormffndstatus,'INCART') ormffndstatus, COALESCE(s.ormffundordelstrtyp,'BSMFsell') ormffundordelstrtyp,
                                                                COALESCE(s.ormffundordelsstdt,'0') ormffundordelsstdt, COALESCE(s.ormffundordelsfreq,'0') ormffundordelsfreq,
                                                                COALESCE(s.ormffundordelsamt,0) ormffundordelsamt, COALESCE(s.ormfsipinstal,0) ormfsipinstal,
                                                    from (select 1 as x) x 
                                                    left join s on x.x = 1
                                                        )
                                                    as d) as ormffundorderlists 
                                            from webapp.pfmflist ls where ls.orportfolioid in (SELECT distinct dpos_pfportfolioid FROM portport) 
                                            and ls.ormffndcode in (SELECT distinct dpos_schemecd FROM portport) 
                                            AND ls.ormfprodtype = 'BSEMF'  AND ls.orpfuserid = '0YzmOxwmwjZM1i7ZCLY5hLfn7SG3' AND ls.entityid = 'IN'
                                            ) 
                                        
                                ) art;
    '''


    cur, dbqerr = db.mydbfunc(con,cur,command)
    print("#########################################3")
    print(command)
    print("#########################################3")
    print(cur)
    print(dbqerr)
    print(type(dbqerr))
    print(dbqerr['natstatus'])
    print(cur.rowcount)
    
    if cur.closed == True:
        if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
            status = "dbfail"
            failreason = "order data fetch failed with DB error"
            print(status,failreason)

    if cur.rowcount > 1:
        status = "dbfail"
        failreason = "order data fetch returned more rows"
        print(status,failreason)

    if cur.rowcount == 1:
        record = cur.fetchall()[0][0]
        print("print success records")
        print(record) 

    print("order details returned for user: "+ userid + "  product :" + product + " trantype: " + trantype)

    placeorderrec = {
    'orderdata'   :     [] if record == None else record,
    'status'      :     'success' if status == None else status,
    'failreason'  :     '' if failreason == None else failreason
    }

    return placeorderrec,status,failreason

@app.route('/mfordersave1',methods=['GET','POST','OPTIONS'])
#example for model code http://www.postgresqltutorial.com/postgresql-python/transaction/
def mfordersave1():
    
    if request.method=='OPTIONS':
        print ("inside ordersave options")
        return jsonify({'body':'success'})

    elif request.method=='POST':   
        print ("inside ordersave post")
        print("--------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        print(request.content_length)
        print("--------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        print(request.headers)
        payload= request.get_json()
        #payload = request.stream.read().decode('utf8')    
        
        pfdatas = payload
        print(pfdatas)
        
        userid,entityid=jwtnoverify.validatetoken(request)
        affected_pfids = []
        affected_schemeids = []
        affected_orderids = []

        for pfdata in pfdatas:
            schmedatas = []
            orderdatas = []
            print("pfdata before removing")
            print(pfdata)
            savetype = None
            status = -1
            neworder_seqnum = 1
            failreason = None

            pfid = pfdata.get('pfportfolioid',None)

            incartscreens = {'BSEMFbuy','BSEMFsell'}

            screenid = pfdata.get('pfscreen',None)

            schmedatas, resp_status, resp_failreason = get_after_validate_schemedata(pfdata, screenid)
            status, failreason  = get_status(status, resp_status, failreason, resp_failreason)

            con,cur=db.mydbopncon()
            command = cur.mogrify("BEGIN;")
            cur, dbqerr = db.mydbfunc(con,cur,command)
            if cur.closed == True:
                if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
                    dbqerr['statusdetails']="DB query failed, BEING failed"
                status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                print(status," : ", failreason)
                resp = make_response(jsonify(dbqerr), 400)
                return(resp)
            print("starting screen filters")
            print(screenid)
            if screenid == "pfs":
                
                if pfid == "NEW":
                    savetype = "New"
                    #Add new pf for the user                    
                    resp_status,resp_failreason = add_new_pf(pfdata, con, cur, userid, entityid)
                    status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                    if status > -1:
                        command = cur.mogrify("ROLLBACK;")
                        cur, dbqerr = db.mydbfunc(con,cur,command)
                        db.mydbcloseall(con, cur)
                        resp = make_response(jsonify(failreason), 400)
                        return(resp)

                    #Add new scheme for the user
                    for schmedata in schmedatas:
                        orderdatas, resp_status, resp_failreason = get_after_validate_orderdata(schmedata,screenid)
                        status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                        if status > -1:
                            command = cur.mogrify("ROLLBACK;")
                            cur, dbqerr = db.mydbfunc(con,cur,command)
                            db.mydbcloseall(con, cur)
                            resp = make_response(jsonify(failreason), 400)
                            return(resp)
                        
                        scheme_code, resp_status,resp_failreason = add_new_scheme(pfdata, schmedata, screenid, entityid, userid, con, cur)
                        status, failreason  = get_status(status, resp_status, failreason, resp_failreason) 
                        if status > -1:
                            command = cur.mogrify("ROLLBACK;")
                            cur, dbqerr = db.mydbfunc(con,cur,command)
                            db.mydbcloseall(con, cur)
                            resp = make_response(jsonify(failreason), 400)
                            return(resp)
                        
                        #Add new order for the user
                        for orderdata in orderdatas:
                            orderid,resp_status,resp_failreason = add_new_order(pfdata, schmedata, orderdata, screenid, con, cur, userid, entityid, neworder_seqnum)
                            status, failreason  = get_status(status, resp_status, failreason, resp_failreason) 
                            if status > -1:
                                resp = make_response(jsonify(failreason), 400)
                                return(resp)

                elif pfid:
                    savetype = "Old"
                    #Update existing pf for the user   
                    resp_status,resp_failreason = update_existing_pf()
                    status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                    
                    # Add new scheme for the user
                    # or
                    # Update existing schme for the user
                    #       ## Add new order for the user
                    #       ## or
                    #       ## Update existing order for the user
                else:
                    new_failreason = "screenid not sent in the submitted record"
                    status, failreason  = get_status(status, 0, failreason, new_failreason)                    
                    print(status,failreason)  

            # IF CON, CUR sent to a function rollback should happen there else rollback to be included in main function

            elif screenid == "ordBSEMFbuy":
                print(pfid)
                if pfid == "NEW" or pfid == None:
                    new_failreason = "porfolio id missing in submitted record"
                    status, failreason = get_status(status, 0, failreason, new_failreason)              
                    print(status,failreason)

                if status < 0:
                    # Loop through Schemedata
                    for schmedata in schmedatas:
                        print("getting orderdata")
                        print("schemdata : ",schmedata)
                        orderdatas, resp_status, resp_failreason = get_after_validate_orderdata(schmedata,screenid)
                        status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                        if status > -1:
                            command = cur.mogrify("ROLLBACK;")
                            cur, dbqerr = db.mydbfunc(con,cur,command)
                            db.mydbcloseall(con, cur)
                            resp = make_response(jsonify(failreason), 400)
                            return(resp)
                        print("getting orderdata complete")
                        print(orderdatas)
                        # ADD or UPDATE SchemeData for the user's portfolio
                        # check if the schme id already exists
                        schm_code, resp_status, resp_failreason  = check_scheme_exists(pfdata, schmedata, con, cur, userid, entityid)
                        status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                        print(schm_code)
                        if status < 0:
                            if schm_code != "" or schm_code == None:
                                # Existing Scheme update
                                print("shcme update")
                                resp_status,resp_failreason = update_existing_scheme(pfdata, schmedata, screenid, con, cur, userid, entityid)
                                status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                            elif schm_code == "":
                                # New Scheme addition
                                print("shcme addition")
                                schm_code, resp_status,resp_failreason = add_new_scheme(pfdata, schmedata, screenid, entityid, userid, con, cur)
                                status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                            else:
                                print("schme else")
                                pass
                            print("after schme tasks : ", status, "ra: ", failreason)
                            if status >= -1:
                                resp = make_response(jsonify(failreason), 400)
                                return(resp)
                            else:
                                affected_schemeids.append(schm_code)
                        else:
                            resp = make_response(jsonify(failreason), 400)
                            return(resp)
                        print("to start with orderdata")

                        for orderdata in orderdatas:
                            print("looping through orderdatas")
                            print(orderdata)
                            #Validate BSEMF sell qty with order qty                         
                            orderid = orderdata.get('orormfpflistid',None)
                            print(orderid)
                            if orderid:
                                # Existing order update                                        
                                resp_status,resp_failreason = update_existing_order(orderdata, screenid, entityid, con, cur)
                                status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                            else:
                                # New order addition
                                orderid,resp_status,resp_failreason = add_new_order(pfdata, schmedata, orderdata, screenid, con, cur, userid, entityid, neworder_seqnum)
                                status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                                print("back to main after orderinsert")
                                print(status, failreason)

                            if status >= -1:
                                resp = make_response(jsonify(failreason), 400)
                                return(resp)
                            else:
                                affected_orderids.append(orderid)

            elif screenid == "ordBSEMFsell":
                print(pfid)
                if pfid == "NEW" or pfid == None:
                    new_failreason = "porfolio id missing in submitted record"
                    status, failreason = get_status(status, 0, failreason, new_failreason)              
                    print(status,failreason)

                if status < 0:
                    #Update existing order under the scheme
                    for schmedata in schmedatas:
                        print("getting orderdata")
                        print("schemdata : ",schmedata)
                        orderdatas, resp_status, resp_failreason = get_after_validate_orderdata(schmedata,screenid)
                        status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                        if status > -1:
                            command = cur.mogrify("ROLLBACK;")
                            cur, dbqerr = db.mydbfunc(con,cur,command)
                            db.mydbcloseall(con, cur)
                            resp = make_response(jsonify(failreason), 400)
                            return(resp)
                        print("getting orderdata complete")
                        print(orderdatas)
                        #ADD or UPDATE order for the user's portfolio
                        
                        for orderdata in orderdatas:
                            print("looping through orderdatas")
                            print(orderdata)
                            if orderdata['orderselect'] == True:
                                #Validate BSEMF sell qty with order qty
                                if orderdata['ormffundordunit'] > (schmedata['dailyposition']['dpos_unit'] + schmedata['dailyposition']['dpos_unitblocked']):
                                    status, failreason  = get_status(status, 0, failreason, "Ordered units are more than available units")                            
                                orderid = orderdata.get('orormfpflistid',None)
                                print(orderid)
                                if status < -1:                          
                                    if orderid:
                                        # Existing order update                                        
                                        resp_status,resp_failreason = update_existing_order(orderdata, screenid, entityid, con, cur)
                                        status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                                    else:
                                        # New order addition
                                        orderid,resp_status,resp_failreason = add_new_order(pfdata, schmedata, orderdata, screenid, con, cur, userid, entityid, neworder_seqnum)
                                        status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
                                        print("back to main after orderinsert")
                                        print(status, failreason)

                                if status >= -1:
                                    resp = make_response(jsonify(failreason), 400)
                                    return(resp)
                                else:
                                    affected_orderids.append(orderid)

            elif screenid in incartscreens:
                filterstr = "INCART"
            elif screenid == None:
                status = "datafail"
                failreason = "screenid not sent in the submitted record"
                print(status,failreason)
            else:
                filterstr = "INCART"
            print(affected_orderids)
            #Cleanup calls
            affected_orderids = affected_orderids if len(affected_orderids) > 0 else None
            resp_status,resp_failreason = cleanup_post_order_task(pfdata, screenid, con, cur, affected_orderids)
            status, failreason  = get_status(status, resp_status, failreason, resp_failreason)
            print("back to main after cleanup")
            print(status, failreason)
            #Cleanup calls end
        
        print("commit")
        db.mydbcloseall(con, cur)

        return jsonify({'natstatus':'success','statusdetails':'Order details for ' + userid +' Saved/Updated'})


def check_scheme_exists(pfdata, d, con, cur, userid, entityid):
    status = -1
    failreason = None
    command = cur.mogrify("""
        SELECT ormflistid FROM webapp.pfmflist WHERE ormffndcode = %s AND orpfuserid = %s AND orportfolioid = %s AND entityid =%s;
        """,(d.get('ormffndcode'),userid,pfdata.get('pfportfolioid'),entityid,))
    print(command)
    cur, dbqerr = db.mydbfunc(con,cur,command)
                        
    if cur.closed == True:
        if(dbqerr['natstatus'] == "error"):
            dbqerr['statusdetails']="Fund exists in PF check failed.  Contact support"
            s, f = get_status(status, 1, failreason, dbqerr['statusdetails'])
            return (None, s, f)

    #Model to follow in all fetch
    if cur.rowcount == 1:
        for record in cur:  
            d['ormflistid'] = record[0]                                

    elif cur.rowcount == 0:
        print("Fund doesn't exist in this users portfolio")
        d['ormflistid'] = ""
    else:
        command = cur.mogrify("ROLLBACK;")
        cur, dbqerr = db.mydbfunc(con,cur,command)
        s, f = get_status(status, 0, failreason, "Same fund exists multiple times in the portfolio")
        return (None, s, f)

    print("is the fund already exists:")
    print(d['ormflistid'])

    if status < 0:
        s, f = get_status(status, -3, failreason , "success")
        return (d['ormflistid'], s, f)
    else:
        s, f = get_status(status, None, failreason , "failed")
        return (None, s, f)

def cleanup_post_order_task(pfdata, screenid, con, cur, affected_orderids = None):
    print("insder post action cleanup")
    print(affected_orderids)
    status = -3
    sql_str = None
    failreason = "success"
    command = None

    if screenid == "ordBSEMFsell":
        delstatu = "INCART"
        whatstatus = "R"
        prod = "BSEMF"
    if screenid == "ordBSEMFbuy":
        delstatu = "INCART"
        whatstatus = "P"
        prod = "BSEMF"
    if screenid == "ordpf":
        delstatu="NEW"
        whatstatus = "%"
        prod = "BSEMF"

    #orderids Cleanup
    sql_str = "DELETE FROM webapp.pfmforlist WHERE entityid =%s AND ororpfuserid = %s AND ororportfolioid = %s AND ormffndstatus = %s AND orormfprodtype = %s"

    if screenid == "ordpf":
        sql_str = sql_str + " AND orormfwhattran LIKE %s"
    else:
        sql_str = sql_str + " AND orormfwhattran IN (%s)"
    
    if affected_orderids:
        if len(affected_orderids):
            #Delete only the order data that are deleted in front end
            sql_str = sql_str + " AND orormfpflistid NOT IN %s"
            print(sql_str)
            command = cur.mogrify(sql_str,(pfdata['entityid'],pfdata['pfuserid'],pfdata['pfportfolioid'],delstatu,prod,whatstatus,tuple(affected_orderids),))
    else:
        print(sql_str)
        print("sle")
        # Delete all the order data as all the order deleted in front end
        command = cur.mogrify(sql_str,(pfdata['entityid'],pfdata['pfuserid'],pfdata['pfportfolioid'],delstatu,prod,whatstatus,))

    print(command)       
    if command:
        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
        
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error"):
                dbqerr['statusdetails']="Couldn't cleanup order post save.  Contact support"
                return (get_status(status, 1, failreason, dbqerr['statusdetails']))

    #scheme Cleanup
    # Delete all the schemes where you don't have any orders (irrespective of their status)
    sql_str = ""
    sql_str = sql_str + " "
    
    command = cur.mogrify("""
                            DELETE FROM webapp.pfmflist WHERE entityid =%s AND orpfuserid = %s AND orportfolioid = %s  AND ormfprodtype = %s
                            AND ormflistid NOT IN (SELECT DISTINCT orormflistid FROM webapp.pfmforlist WHERE entityid =%s AND ororpfuserid = %s AND ororportfolioid = %s AND orormfprodtype = %s)
            """,(pfdata['entityid'],pfdata['pfuserid'],pfdata['pfportfolioid'],prod,pfdata['entityid'],pfdata['pfuserid'],pfdata['pfportfolioid'],prod,))

    print(command)       
    if command:
        print(command)
        cur, dbqerr = db.mydbfunc(con,cur,command)
        
        if cur.closed == True:
            if(dbqerr['natstatus'] == "error"):
                dbqerr['statusdetails']="Couldn't cleanup order post save.  Contact support"
                return (get_status(status, 1, failreason, dbqerr['statusdetails']))

    if status < 0:
        return (get_status(status, -3, failreason , "success"))
    else:
        return (get_status(status, None, failreason , "success"))

def get_after_validate_schemedata(pfdata, prod_type):
    status = -3
    failreason = "success"
    print(prod_type)
    schmedatas = None
    if prod_type == "ordBSEMFbuy" or prod_type == "ordBSEMFsell":
        if 'pfmflist' in pfdata:
            schmedatas = pfdata.pop("pfmflist")
            print("schmedatas ordBSEMF")
            print(schmedatas)
        else:
            schmedatas = None

    elif prod_type == "ordEQbuy" or prod_type == "ordEQsell":
        if 'pfstklist' in pfdata:
            schmedatas = pfdata.pop("pfmflist")
            print("schmedatas")
            print(schmedatas)
        else:
            schmedatas = None
    
    if schmedatas == None:
        failreason = "scheme data key missin in the submitted record"
        status = 0
        print(status,failreason)
    print("returning schemedatas")
    return schmedatas, status, failreason

def get_after_validate_orderdata(schemedata, screenid):
    orderdata = None
    status = -3
    failreason = "success"
    if screenid == "ordBSEMFbuy" or screenid == "ordBSEMFsell":
        if 'ormffundorderlists' in schemedata:
            orderdata = schemedata.pop("ormffundorderlists")
            print("Insider orderdata get")
            print(orderdata)
        else:
            orderdata = None

    elif screenid == "EQbuy" or screenid == "EQsell":
        if 'ormffundorderlists' in schemedata:
            orderdata = schemedata.pop("pfmflist")
            print("orderdata")
            print(orderdata)
        else:
            orderdata = None
    
    if orderdata == None:
        failreason = "order data key missin in the submitted record"
        status = 0
        print(status,failreason)

    return orderdata, status, failreason

def add_new_pf(pfdata, con, cur, userid, entityid):
    print('inside add New pf')
    useridstr = userid
    pfsavetimestamp= datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    pfdata['pfoctime']= pfsavetimestamp
    pfdata['pflmtime']= pfsavetimestamp
    status = None
    failreason = None

    print('MAX query')
    command = cur.mogrify("SELECT MAX(pfpfidusrrunno) FROM webapp.pfmaindetail where pfuserid = %s",(useridstr,))
    cur, dbqerr = db.mydbfunc(con,cur,command)

    if cur.closed == True:
        if(dbqerr['natstatus'] == "error"):
            dbqerr['statusdetails'] = "Max Number identification Failed"
            return (get_status(status, 1, failreason, dbqerr['statusdetails']))
    
    record = None
    if cur.rowcount == 1:
        record = cur.fetchall()

    print("iam printing records to see")
    print(record)
    
    if record:
        if record[0] == None:
            pfmainnextmaxval = 1
        else:
            if(type(record[0]) == "Decimal"):
                pfmainnextmaxval = int(Decimal(record[0]))+1                                
            else:
                pfmainnextmaxval = record[0] + 1
    else:
        command = cur.mogrify("ROLLBACK;")
        cur, dbqerr = db.mydbfunc(con,cur,command)
        return (get_status(status, 0, failreason, "Max Number fetch returned mutiple rows"))

    pfdata['pfpfidusrrunno'] = str(pfmainnextmaxval)
    pfdata['pfportfolioid'] = useridstr + str(pfmainnextmaxval)
    
    if pfdata.get('pfbeneusers') == None:
        pfdata['pfbeneusers'] = useridstr
    
    pfdata['entityid'] = entityid

    pfdatajsondict = json.dumps(pfdata)

    command = cur.mogrify("INSERT INTO webapp.pfmaindetail select * from json_populate_record(NULL::webapp.pfmaindetail,%s);",(str(pfdatajsondict),))
    print(command)
    cur, dbqerr = db.mydbfunc(con,cur,command)
    if cur.closed == True:
        if(dbqerr['natstatus'] == "error"):
            dbqerr['statusdetails']="Couldn't save Porfolio (main insert  Failed).  Contact support"
            return (get_status(status, 1, failreason, dbqerr['statusdetails']))

    if status < 0:
        return (get_status(status, -3, failreason , "success"))
    else:
        return (get_status(status, None, failreason , "success"))

def update_existing_pf():
    return 'ok'

def add_new_scheme(pfdata, d, prod_trantype, entityid, userid, con, cur): 
    #taking tran type here to accomodate short sell ie...selling a scheme before buying (going short)
    #New Scheme getting added to the PF
    print("PRINTING add new scheme")
    print(d)
    status = -1
    failreason = None   
    pfid = pfdata.get('pfportfolioid')
    newschmem_seqnum = get_new_seq("BSEMFscheme",entityid, userid, pfid, None, con, cur)
    pfsavetimestamp= datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    d['ormfoctime'] = pfsavetimestamp
    d['ormflmtime'] = pfsavetimestamp
    d['ormflistid'] = 'mf'+ pfid + str(newschmem_seqnum)
    d['orportfolioid'] = pfid
    d['entityid'] = entityid
    d['ormfseqnum'] = str(newschmem_seqnum)
    d['orpfuserid'] = userid
    # pfmflsdatalist.apend(d['ormflistid'])

    pfmflsdatajsondict = json.dumps(d)
    command = cur.mogrify("INSERT INTO webapp.pfmflist select * from json_populate_record(NULL::webapp.pfmflist,%s) where entityid = %s;",(str(pfmflsdatajsondict),entityid,))
    print(command)                
    cur, dbqerr = db.mydbfunc(con,cur,command)
    if cur.closed == True:
        if(dbqerr['natstatus'] == "error"):
            dbqerr['statusdetails']="Couldn't save schemedata (new order insert  Failed).  Contact support"
            print(status, 1, dbqerr['statusdetails'], failreason)
            s, f = get_status(status, 1, failreason, dbqerr['statusdetails'])
            return (None, s, f)
    print("new scheme insert complete")

    if status < 0:
        s, f = get_status(status, -3, failreason , "success")
        return (d['ormflistid'],s,f )
    else:
        s, f = get_status(status, None, failreason , "failure")
        return (None, s, f)

def update_existing_scheme(pfdata, d, prod_trantype, con, cur, userid, entityid):
    status = -1
    failreason = None
    d['entityid']=entityid
    d['orpfuserid']=pfdata.get('pfuserid')
    d['ormflmtime'] = datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    schemedata_json = json.dumps(d)
    #command = cur.mogrify("UPDATE webapp.pfmflist select * from json_populate_record(NULL::webapp.pfmflist,%s) WHERE ormflistid =%s AND entityid = %s;",(str(pfmflsdatajsondict),d.get('ormflistid'),entityid,))
    
    #donot update if the fund is fixed : START
    if(d['ormffndnameedit'] != 'fixed'):
        command = cur.mogrify("""
                    UPDATE webapp.pfmflist set(ormffundname,ormffndcode,ormffndnameedit,ormfdathold,ormflmtime) = 
                    (select ormffundname,ormffndcode,ormffndnameedit,ormfdathold,ormflmtime from json_to_record (%s)
                    AS (ormffundname varchar(100),ormffndcode varchar(100),ormffndnameedit varchar(100),ormfdathold text,ormflmtime timestamp))
                    WHERE ormflistid =%s AND entityid = %s;
                """,(str(schemedata_json),d.get('ormflistid'),entityid,))                       
        print(command)                
        cur, dbqerr = db.mydbfunc(con,cur,command)

        if cur.closed == True:
            if(dbqerr['natstatus'] == "error"):
                dbqerr['statusdetails']="Couldn't update scheme.  Contact support"
                return (get_status(status, 1, failreason, dbqerr['statusdetails']))
    
    #donot update if the fund is fixed : END
    
    if status < 0:
        return (get_status(status, -3, failreason , "success"))
    else:
        return (get_status(status, None, failreason , "failed"))
    
#add_new_order(pfdata,schemedata,orderdata,screenid)
def add_new_order(p, d, e, prod_trantype, con, cur, userid, entityid, neworder_seqnum):
    print("PRINTING add new order")
    print(e)
    status = -1
    failreason = None    
    print(p,d,e)
    print("check check check")
    pfsavetimestamp= datetime.now().strftime('%Y/%m/%d %H:%M:%S')
    e['orormflistid']= d.get('ormflistid',None)                 
    e['ormfoctime']= pfsavetimestamp
    e['ormflmtime']= pfsavetimestamp    
    e['ororportfolioid'] = p.get('pfportfolioid')
    e['orpfportfolioname']= p.get('pfportfolioname')
    e['ororpfuserid'] = userid
    e['orormffundname']=d.get('ormffundname')
    e['orormffndcode']=d.get('ormffndcode')
    e['ororfndamcnatcode']=d.get('ormfnatamccode')
    e['entityid'] = entityid   
    neworder_seqnum = get_new_seq("BSEMForder", entityid, userid, e['ororportfolioid'], e['orormflistid'], con, cur)
    e['orormfpflistid']= "or" + d.get('ormflistid',None) + str(neworder_seqnum)
    e['orormfseqnum'] = neworder_seqnum
    print(e)
    orderdata_json = json.dumps(e)
    print(e['ormffundordelsstdt'])

    if(e.get('ormffundordelsstdt')==0):
        if (e['ormffundordelstrtyp'] == "SIP"):
            s, f = get_status(status, 0, failreason , "SIP START DATE is Mandatory")
            return (None, s, f)

    command = cur.mogrify("INSERT INTO webapp.pfmforlist select * from json_populate_record(NULL::webapp.pfmforlist,%s);",(str(orderdata_json),))
    print(command)
    cur, dbqerr = db.mydbfunc(con,cur,command)
    if cur.closed == True:
        if(dbqerr['natstatus'] == "error"):
            dbqerr['statusdetails']="Couldn't save orderdata (order insert  Failed).  Contact support"
            print(status, 1, dbqerr['statusdetails'], failreason)
            s, f = get_status(status, 1, failreason, dbqerr['statusdetails'])
            return (None, s, f)
    print("new order insert complete")
    print(status, 1, dbqerr['statusdetails'], failreason)
    print(e['orormfpflistid'], get_status(status, -3, failreason , "success"))
    if status < 0:
        s, f = get_status(status, -3, failreason , "success")
        return (e['orormfpflistid'],s,f )
    else:
        s, f = get_status(status, None, failreason , "failure")
        return (None, s, f)



def get_new_seq(reqseqfor,entityid, userid, pfid, schmid, con, cur):

    if reqseqfor == "BSEMForder":
        command = cur.mogrify("""
                SELECT MAX(orormfseqnum) FROM webapp.pfmforlist 
                WHERE entityid =%s AND ororpfuserid = %s AND ororportfolioid = %s AND orormflistid = %s;
                """,(entityid,userid,pfid,schmid,))
    elif reqseqfor == "BSEMFscheme":
        command = cur.mogrify("""
                        SELECT MAX(ormfseqnum) FROM webapp.pfmflist where orportfolioid = %s AND orpfuserid = %s AND entityid =%s;
                    """,(pfid ,userid, entityid,))

    print(command)
    cur, dbqerr = db.mydbfunc(con,cur,command)
                        
    if cur.closed == True:
        if(dbqerr['natstatus'] == "error" or dbqerr['natstatus'] == "warning"):
            dbqerr['statusdetails']="Fund MAX sequence fetch failed"
        resp = make_response(jsonify(dbqerr), 400)
        return(resp)

    #Model to follow in all fetch
    records=[]
    for record in cur:  
        records.append(record[0])
    print("iam printing records to see")
    print(records)
    
    if(records[0] == None):
        newseq = 1
    else:
        if(type(records[0])=="Decimal"):
            newseq = int(Decimal(records[0]))+1                                
        else:
            newseq = records[0]+1
    print(int(newseq))
    return int(newseq)

def update_existing_order(orderdata, prod_trantype, entityid, con, cur):
    status = -1
    failreason = None
    if prod_trantype == "ordBSEMFsell":
        command = cur.mogrify("""
            UPDATE webapp.pfmforlist SET ormffundordunit = %s 
            WHERE orormfpflistid = %s AND orormflistid = %s AND ororportfolioid = %s AND ororpfuserid = %s AND entityid = %s
        """,(orderdata['ormffundordunit'],orderdata['orormfpflistid'],orderdata['orormflistid'],orderdata['ororportfolioid'],orderdata['ororpfuserid'],orderdata['entityid'],))

    elif prod_trantype == "ordBSEMFbuy":
        pfmflsordatajsondict = json.dumps(orderdata)           
        #Record which are only editable to be updated.
        if(orderdata['ormffndstatus'] == 'New'):   
            command = cur.mogrify("""
                        UPDATE webapp.pfmforlist set(orormffundname,orormffndcode,ormffundordelsfreq,ormffundordelsstdt,ormffundordelsamt,ormfsipinstal,ormfsipendt,ormfsipdthold,ormfselctedsip,ormffndstatus,ormflmtime) = 
                        (select orormffundname,orormffndcode,ormffundordelsfreq,ormffundordelsstdt,ormffundordelsamt,ormfsipinstal,ormfsipendt,ormfsipdthold,ormfselctedsip,ormffndstatus,ormflmtime from json_to_record (%s)
                        AS (orormffundname varchar(100),orormffndcode varchar(100),ormffundordelsfreq varchar(20),ormffundordelsstdt varchar(11),ormffundordelsamt numeric(16,5),ormfsipinstal numeric(3),ormfsipendt date,ormfsipdthold text,ormfselctedsip text,ormffndstatus varchar(10),ormflmtime timestamp))
                        WHERE orormfpflistid = %s AND entityid = %s;
                    """,(str(pfmflsordatajsondict),orderdata.get('orormfpflistid'),entityid,))

        elif(orderdata['ormffndstatus']=='INCART'):   
            command = cur.mogrify("""
                        UPDATE webapp.pfmforlist set(orormffundname,orormffndcode,ormffundordelsfreq,ormffundordelsstdt,ormffundordelsamt,ormfsipinstal,ormfsipendt,ormfsipdthold,ormfselctedsip,ormffndstatus,ormflmtime) = 
                        (select orormffundname,orormffndcode,ormffundordelsfreq,ormffundordelsstdt,ormffundordelsamt,ormfsipinstal,ormfsipendt,ormfsipdthold,ormfselctedsip,ormffndstatus,ormflmtime from json_to_record (%s)
                        AS (orormffundname varchar(100),orormffndcode varchar(100),ormffundordelsfreq varchar(20),ormffundordelsstdt varchar(11),ormffundordelsamt numeric(16,5),ormfsipinstal numeric(3),ormfsipendt date,ormfsipdthold text,ormfselctedsip text,ormffndstatus varchar(10),ormflmtime timestamp))
                        WHERE orormfpflistid = %s AND entityid = %s;
                    """,(str(pfmflsordatajsondict),orderdata.get('orormfpflistid'),entityid,))
        else:
            pass

    print(command)
    cur, dbqerr = db.mydbfunc(con,cur,command)
    if cur.closed == True:
        if(dbqerr['natstatus'] == "error"):
            dbqerr['statusdetails']="Couldn't update orderdata.  Contact support"
            print(status, 1, dbqerr['statusdetails'], failreason)
            return (get_status(status, 1, failreason, dbqerr['statusdetails']))
    print("order update complete")
    print(status, 1, dbqerr['statusdetails'], failreason)
    if status == status < 0:
        return (get_status(status, -3, failreason , "success"))
    else:
        return (get_status(status, None, failreason , "failure"))

def get_status(curstatus,newstatus,curreason, newreason):
    '''
    status =   
                -3 --> success
                -1 --> empty
                0  --> data error
                1  --> db error
                2  --> both data and db error
    '''
    print(curstatus,newstatus,curreason, newreason)
    if curstatus == None:
        curstatus = -1

    setstatus = -1
    
    if newstatus == -3:
        setstatus = -3
        setreason = None
    else:
        if curstatus < 0:
            setstatus = newstatus
        elif curstatus == 2:
            setstatus = curstatus
        elif curstatus == newstatus:
            setstatus = curstatus
        elif curstatus != newstatus:
            setstatus = 2

        if curreason and setstatus > -1:
            setreason = curreason + " | " + newreason
        else:
            setreason = newreason

    return -1 if setstatus == None else setstatus, setreason