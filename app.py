from flask import Flask, json, Response, request, render_template
from werkzeug.utils import secure_filename
from os import path, getcwd
import time
from face import Face
import sqlite3 as sql

app = Flask(__name__)

app.config['file_allowed'] = ['image/png', 'image/jpeg']
app.config['storage'] = path.join(getcwd(), 'storage')
app.face = Face(app)


def success_handle(output, status=200, mimetype='application/json'):
    return Response(output, status=status, mimetype=mimetype)


def error_handle(error_message, status=500, mimetype='application/json'):
    return Response(json.dumps({"error": {"message": error_message}}), status=status, mimetype=mimetype)


def get_user_by_id(user_id):
    user = {}
    with sql.connect("database.db") as con:
        cur = con.cursor()
        results = cur.execute("SELECT users.id, users.name, users.created, faces.id, faces.user_id, faces.filename,faces.created FROM users LEFT JOIN faces ON faces.user_id = users.id WHERE users.id = "+str(user_id))
        index = 0
        for row in results:
            # print(row)
            face = {
                "id": row[3],
                "user_id": row[4],
                "filename": row[5],
                "created": row[6],
            }
            if index == 0:
                user = {
                    "id": row[0],
                    "name": row[1],
                    "created": row[2],
                    "faces": [],
                }
            if row[3]:
                user["faces"].append(face)
            index = index + 1
    con.close()

    if 'id' in user:
        return user
    return None


def delete_user_by_id(user_id):
    app.db.delete('DELETE FROM users WHERE users.id = ?', [user_id])
    # also delete all faces with user id
    app.db.delete('DELETE FROM faces WHERE faces.user_id = ?', [user_id])


@app.route('/api', methods=['GET'])
def homepage():
    output = json.dumps({"api": '1.0'})
    return success_handle(output)


@app.route('/api/user_registration', methods=['POST'])
def user_registration():
    output = json.dumps({"success": True})

    if 'file' not in request.files:
        return error_handle("Missing Face Image.")
    else:

        print("File request", request.files)
        file = request.files['file']

        if file.mimetype not in app.config['file_allowed']:

            return error_handle("Invalid file extension. Valid Files[*.png , *.jpg]")
        else:

            name = request.form['name']
            filename = secure_filename(file.filename)
            trained_storage = path.join(app.config['storage'], 'trained')
            file.save(path.join(trained_storage, filename))
            
            created = int(time.time())
            with sql.connect("database.db") as con:
                cur = con.cursor()
                cur.execute('INSERT INTO users(name, created) values(?,?)', (name, created))
                user_id = cur.lastrowid
                if user_id:
                    print("User saved in data", name, user_id)
                    
                    cur2 = con.cursor()
                    cur2.execute('INSERT INTO faces(user_id, filename, created) values(?,?,?)',
                                 [user_id, trained_storage+"/"+filename, created])
                    face_id = cur2.lastrowid

                    if face_id:
                        face_data = {"id": face_id, "filename": name + ".jpg", "created": created}
                        return_output = json.dumps({"id": user_id, "name": name, "face": [face_data]})
                        con.commit()
                        return success_handle(return_output)
                    else:

                        return error_handle("Error while saving face")
            con.close()
    return success_handle(output)


# route for user profile
@app.route('/api/users/<int:user_id>', methods=['GET', 'DELETE'])
def user_profile(user_id):
    if request.method == 'GET':
        user = get_user_by_id(user_id)
        if user:
            return success_handle(json.dumps(user), 200)
        else:
            return error_handle("User does not exist", 404)
    if request.method == 'DELETE':
        delete_user_by_id(user_id)
        return success_handle(json.dumps({"deleted": True}))


# router for recognize a unknown face
@app.route('/api/recognize', methods=['POST'])
def recognize():
    if 'file' not in request.files:
        return error_handle("Missing Face Image.")
    else:
        file = request.files['file']
        # file extension valiate
        if file.mimetype not in app.config['file_allowed']:
            return error_handle("File extension is not allowed")
        else:

            filename = secure_filename(file.filename)
            unknown_storage = path.join(app.config["storage"], 'unknown')
            file_path = path.join(unknown_storage, filename)
            file.save(file_path)

            user_id = app.face.recognize(filename)
            if user_id:
                user = get_user_by_id(user_id)
                message = {"message": "Welcome {0} !!".format(user["name"]),
                           "user": user}
                return success_handle(json.dumps(message))
            else:

                return error_handle("Unrecognised User")


# Run the app
app.run()