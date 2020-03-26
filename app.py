import os
from flask import Flask
from flask import request
import json
from flask_cors import CORS, cross_origin
import pymongo
import sys
from werkzeug import secure_filename
import pandas as pd
import time
import random
import string
import requests
from datetime import datetime
from datetime import timedelta
from dateutil import parser
import copy

app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

# DATABASE CONNECTION
try:
    DB_USER = 'ako'
    DB_PASSWORD = 'secret123'
    db_client = pymongo.MongoClient('mongodb://' + DB_USER + ':' + DB_PASSWORD + '@ds060749.mlab.com:60749/sramako_qtest?retryWrites=false')
    db = db_client["sramako_qtest"]
except:
    print("DB Access FAILED.")


# UPLOAD TEST

@app.route('/uploader', methods = ['POST', 'GET'])
def upload_file():
    if request.method == 'POST':

        # Parse Data
        f = request.files['file']
        group = request.values['group']
        test = request.values['test']

        # Save File
        f.save('upload/file.xlsx')

        # Parse File
        f = pd.read_excel('upload/file.xlsx', header=None)
        data = []
        for i, r in f.iterrows():
            q = dict()
            q['id'] = i+1
            q[ 'question' ] = r[0]
            q[ 'answers' ] = [
                { 'id' : 1, 'value' : r[1] },
                { 'id' : 2, 'value' : r[2] },
                { 'id' : 3, 'value' : r[3] },
                { 'id' : 4, 'value' : r[4] },
            ]
            data.append(q)

        n = len(data)
        
        # Save to DB : metadata, questions, group, test
        db_col = db["Tests"]
        db_col.insert_one({
                                'metadata' : n,
                                'questions' : data, 
                                'group' : group, 
                                'test' : test
        })

        return 'Test has been registered.'


    return "    \
<title>Upload Test</title>  \
<h1>Upload Test</h1>    \
<form action='' method='POST' enctype='multipart/form-data'><p> \
        <input type='file' name='file'><br/><br/> \
        Test<br/><input type='text' name='test'><br/>    \
        Group<br/><input type='text' name='group'><br/><br/>    \
        <input type='submit' value='Upload'>    \
</p></form>"


# GET USER'S AVAILABLE TESTS

@app.route('/tests', methods = ['POST'])
def tests():
    if request.method == 'POST':

        # Parse Data
        # email = request.values['email']
        # name = request.values['name']
        # imageUrl = request.values['imageUrl']
        # googleId= request.values['googleId']

        email = ''
        data = json.loads(request.data);
        if 'email' in data:
            email = data["email"]

        # Check if user is registered
        # TODO

        # Get groups that are relevant
        db_col = db["Groups"]
        res = db_col.find( { 'EMAIL' : email }, { '_id':0, 'GROUP':1 } )
        groups = []
        for i in res:
            groups.append(i['GROUP'])
        groups = list(set(groups))
        print(groups)
        
        # Get tests for relevant groups
        db_col = db["Tests"]
        tests = []
        for group in groups:
            temp = db_col.find( { 'group' : group }, { '_id':0, 'test':1 } )
            for i in temp:
                tests.append(( group, i['test'] ))
        tests = list(set(tests))

        # REMOVE COMPLETED/ACTIVE TESTS
        # TODO

        return json.dumps(tests)

@app.route('/status', methods = ['POST'])
def status():
    if request.method == 'POST':

        # Parse Data
        # name = request.values['name']
        # imageUrl = request.values['imageUrl']
        # googleId= request.values['googleId']
        data = json.loads(request.data)
        keys = ['email', 'test', 'group', 'answer']

        statusData = dict()
        for key in keys:
            if key in data:
                statusData[key] = data[key]
            else:
                return "Invalid Payload"

        # Build Collection Record
        query = {
            'EMAIL' :   statusData['email'],
            'TEST'  :   statusData['test'],
            'GROUP' :   statusData['group']
        }
        record = copy.deepcopy(query)

        # Check Test State
        db_col = db["TestResponses"]
        res = db_col.find(
            query,
            {
                '_id'       :   0,
                'ANSWER'    :   1,
                'CLIMAX'    :   1
            }
        )

        # Pending Test
        if res.count()==0:
            climaxHours = 1
            climaxMinutes = 1
            climax = datetime.now() + timedelta( hours=climaxHours, minutes=climaxMinutes )
            record['CLIMAX'] = str(climax)
            record['ANSWER'] = statusData['answer'] # TODOx: Safe copy

            # Write to DB
            db_col.insert_one(
                record
            )
            for i in range(0, len(record["ANSWER"])):
                record["ANSWER"][i] = str(record["ANSWER"][i] )
            return json.dumps({ 'ANSWER' : record["ANSWER"], 'CLIMAX' : record["CLIMAX"] })

        else:
            record = res.next()

            # Active Test
            if parser.parse(record['CLIMAX']) > datetime.now():
                # record['ANSWER'] = statusData['answer'] # TODOx: Safe copy
                for i in range(0, len(statusData['answer'])):
                    if int(statusData['answer'][i]) != -1:
                        record['ANSWER'][i] = statusData['answer'][i]
                # Write to DB
                db_col.update_one(
                    query,
                    {
                        "$set" : { 'ANSWER' : record['ANSWER'] }
                    },
                    upsert = False
                )
                for i in range(0, len(record["ANSWER"])):
                    record["ANSWER"][i] = str(record["ANSWER"][i] )
                return json.dumps({ 'ANSWER' : record["ANSWER"], 'CLIMAX' : record["CLIMAX"] })
        
            # Completed Test
            else:
                return "Test Completed"

# FETCH THE EXAM

@app.route('/metadata', methods = ['POST'])
def metadata():
    if request.method == 'POST':
        data = json.loads(request.data)
        keys = ['email', 'test', 'group']

        statusData = dict()
        for key in keys:
            if key in data:
                statusData[key] = data[key]
            else:
                return "Invalid Payload"

        # Build Collection Record
        query = {
            'test'  :   statusData['test'],
            'group' :   statusData['group']
        }
        record = copy.deepcopy(query)

        # Check Test State
        db_col = db["Tests"]
        res = db_col.find(
            query,
            {
                '_id'       :   0,
                'metadata'    :   1,
                'questions'    :   1
            }
        )

        data = res.next()

        return json.dumps(data)

@app.route('/health', methods = ['GET'])
def health():
    return "Ok"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # app.config['CORS_HEADERS'] = 'Content-Type'
    app.run(host='0.0.0.0', port=port, debug=True)
    # app.run()