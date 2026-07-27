import os
import datetime
import functools
import jwt
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
import pymysql

app = Flask(__name__)
# Clave secreta leída de variable de entorno
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mi_clave_secreta_streamflix')

# Configuración de tu conexión MySQL leyendo de Variables de Entorno
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '192.241.141.69'),
    'user': os.environ.get('DB_USER', 'admindb'),
    'password': os.environ.get('DB_PASSWORD', 'contraseña'),
    'database': os.environ.get('DB_NAME', 'streamingflix'),
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db():
    return pymysql.connect(**DB_CONFIG)

def obtener_tiempo_token():
    try:
        conn = get_db()
        with conn.cursor() as cursor:
            cursor.execute("SELECT valor FROM parametros WHERE clave = 'TOKEN_EXPIRE_MINUTES'")
            res = cursor.fetchone()
            if res:
                return int(res['valor'])
    except Exception as e:
        print("Error obteniendo tiempo de token:", e)
    finally:
        if 'conn' in locals(): conn.close()
    return 15

def crear_token(usuario):
    minutos = obtener_tiempo_token()
    expiracion = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutos)
    return jwt.encode({'usuario': usuario, 'exp': expiracion}, app.config['SECRET_KEY'], algorithm='HS256')

def token_requerido(f):
    @functools.wraps(f)
    def decorado(*args, **kwargs):
        token = request.cookies.get('token')
        if not token:
            return redirect(url_for('login'))
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        except:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorado


# --- VISTAS ---

@app.route('/')
def index():
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM contenidos")
        resultados = cursor.fetchall()
    conn.close()
    return render_template('index.html', contenidos=resultados, titulo_seccion="Todos los Contenidos", seccion_activa="inicio")

@app.route('/peliculas')
def peliculas():
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM contenidos WHERE categoria = 'Película'")
        resultados = cursor.fetchall()
    conn.close()
    return render_template('index.html', contenidos=resultados, titulo_seccion="Películas", seccion_activa="peliculas")

@app.route('/series')
def series():
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM contenidos WHERE categoria = 'Serie'")
        resultados = cursor.fetchall()
    conn.close()
    return render_template('index.html', contenidos=resultados, titulo_seccion="Series", seccion_activa="series")

@app.route('/musica-podcasts')
def musica_podcasts():
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM contenidos WHERE categoria = 'Música / Podcasts'")
        resultados = cursor.fetchall()
    conn.close()
    return render_template('index.html', contenidos=resultados, titulo_seccion="Música / Podcasts", seccion_activa="musica")

@app.route('/reproducir/<int:video_id>')
def reproducir(video_id):
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM contenidos WHERE id = %s", (video_id,))
        video = cursor.fetchone()
    conn.close()

    if not video:
        return "Contenido no encontrado", 404

    return render_template('player.html', video=video)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM usuarios WHERE email=%s AND password=%s", (email, password))
                user = cursor.fetchone()
                if user:
                    token = crear_token(user['nombre'])
                    resp = make_response(redirect(url_for('dashboard')))
                    resp.set_cookie('token', token, httponly=True)
                    return resp
                else:
                    return render_template('login.html', error="Credenciales incorrectas")
        finally:
            conn.close()
            
    return render_template('login.html')

@app.route('/dashboard')
@token_requerido
def dashboard():
    return render_template('dashboard.html')





# --- MÉTODOS DEL TOKEN ---

@app.route('/api/token/verificar')
def verificar_token():
    token = request.cookies.get('token')
    if not token:
        return jsonify({'valido': False}), 401
    try:
        jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return jsonify({'valido': True})
    except:
        return jsonify({'valido': False}), 401

@app.route('/api/token/renovar', methods=['POST'])
def renovar_token():
    nuevo_token = crear_token('Admin')
    resp = make_response(jsonify({'exito': True}))
    resp.set_cookie('token', nuevo_token, httponly=True)
    return resp


# --- CRUD 1: CATÁLOGO DE USUARIOS ---

@app.route('/api/usuarios', methods=['GET', 'POST'])
def crud_usuarios():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if request.method == 'POST':
                data = request.get_json()
                cursor.execute("INSERT INTO usuarios (nombre, email, password, rol) VALUES (%s, %s, %s, %s)",
                               (data['nombre'], data['email'], data['password'], data.get('rol', 'usuario')))
                conn.commit()
                return jsonify({'exito': True})
            else:
                cursor.execute("SELECT id, nombre, email, rol FROM usuarios")
                return jsonify(cursor.fetchall())
    finally:
        conn.close()

@app.route('/api/usuarios/<int:id>', methods=['DELETE'])
def eliminar_usuario(id):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM usuarios WHERE id=%s", (id,))
            conn.commit()
            return jsonify({'exito': True})
    finally:
        conn.close()


# --- CRUD 2: CATÁLOGO DE CONTENIDOS ---

@app.route('/api/contenidos', methods=['GET', 'POST'])
def crud_contenidos():
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            if request.method == 'POST':
                data = request.get_json()
                cursor.execute("INSERT INTO contenidos (titulo, categoria, anio) VALUES (%s, %s, %s)",
                               (data['titulo'], data['categoria'], data['anio']))
                conn.commit()
                return jsonify({'exito': True})
            else:
                cursor.execute("SELECT * FROM contenidos")
                return jsonify(cursor.fetchall())
    finally:
        conn.close()

        

@app.route('/api/contenidos/<int:id>', methods=['DELETE'])
def eliminar_contenido(id):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM contenidos WHERE id=%s", (id,))
            conn.commit()
            return jsonify({'exito': True})
    finally:
        conn.close()

@app.route('/api/contenidos/<int:id>', methods=['GET'])
def get_contenido_individual(id):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, titulo, categoria, anio, imagen_url, video_url FROM contenidos WHERE id = %s", (id,))
            contenido = cursor.fetchone()
            if contenido:
                return jsonify(contenido)
            return jsonify({'error': 'No encontrado'}), 404
    finally:
        conn.close()


@app.route('/api/contenidos/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def manejar_contenido_individual(id):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            # 1. OBTERNER UN CONTENIDO (GET)
            if request.method == 'GET':
                cursor.execute("SELECT id, titulo, categoria, anio, imagen_url, video_url FROM contenidos WHERE id = %s", (id,))
                contenido = cursor.fetchone()
                if contenido:
                    return jsonify(contenido)
                return jsonify({'error': 'Contenido no encontrado'}), 404

            # 2. ACTUALIZAR UN CONTENIDO (PUT)
            elif request.method == 'PUT':
                data = request.get_json()
                cursor.execute(
                    """UPDATE contenidos 
                       SET titulo = %s, categoria = %s, anio = %s, imagen_url = %s, video_url = %s 
                       WHERE id = %s""",
                    (
                        data.get('titulo'),
                        data.get('categoria'),
                        data.get('anio'),
                        data.get('imagen_url', ''),
                        data.get('video_url', ''),
                        id
                    )
                )
                conn.commit()
                return jsonify({'exito': True, 'mensaje': 'Contenido actualizado correctamente'})

            # 3. ELIMINAR UN CONTENIDO (DELETE)
            elif request.method == 'DELETE':
                cursor.execute("DELETE FROM contenidos WHERE id = %s", (id,))
                conn.commit()
                return jsonify({'exito': True, 'mensaje': 'Contenido eliminado correctamente'})

    except Exception as e:
        print(f"Error en /api/contenidos/{id}:", e)
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)
