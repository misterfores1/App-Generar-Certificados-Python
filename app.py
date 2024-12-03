from flask import Flask, render_template, request, send_file, redirect, url_for, session, flash
from fpdf import FPDF
from datetime import datetime, timedelta  # Importar timedelta
from PIL import Image
import sqlite3
import csv
import os
from werkzeug.security import generate_password_hash, check_password_hash







app = Flask(__name__)

# Configuración de la clave secreta para sesiones
app.secret_key = "mi_clave_secreta"

# Configuración del tiempo de vida de la sesión (ejemplo: 30 minutos)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=2)

# Función para conectar con la base de datos
def conectar_bd():
    connection = sqlite3.connect("main.db")
    connection.row_factory = sqlite3.Row  # Para usar nombres de columnas en las filas
    return connection

# Ruta principal: muestra el formulario
@app.route("/")
def index():
    return render_template("index.html")


# Ruta para generar el certificado vieja
@app.route("/generar", methods=["POST"])
def generar_certificado():
    documento = request.form.get("documento")

    # Conectar a la base de datos y obtener los datos
    connection = conectar_bd()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM aprobados WHERE documento = ?", (documento,))
    registro = cursor.fetchone()

    # Si no se encuentra el registro, mostrar una página de error
    if not registro:
        flash("No se encontró el registro para este documento.", "error")
        return redirect(url_for("index"))

    # Extraer los datos del registro
    nombre = registro["nombre"]
    curso = registro["curso"]
    fecha_aprobacion = datetime.now().strftime("%d/%m/%Y")
    id_registro = registro["id"]  # Obtener el ID del registro

    # Marcar como descargado el registro en la base de datos
    cursor.execute("UPDATE aprobados SET descargado = 1 WHERE id = ?", (id_registro,))
    connection.commit()  # Guardar los cambios en la base de datos
    connection.close()  # Cerrar la conexión

    # Cargar la plantilla como imagen
    template_image_path = "static/plantilla_certificado.jpg"  # O usa .png si es el caso
    img = Image.open(template_image_path)

    # Crear el PDF
    pdf_temp = FPDF()
    pdf_temp.add_page()
    
    img_width, img_height = img.size
    img_width_mm = img_width / 72 * 25.4
    img_height_mm = img_height / 72 * 25.4

    pdf_temp.image(template_image_path, x=0, y=0, w=img_width_mm, h=img_height_mm)

    # Agregar texto
    pdf_temp.set_font("Times", size=28)
    pdf_temp.set_xy(50, 100)
    pdf_temp.cell(110, 50, f"{nombre}", align="C")

    pdf_temp.set_font("Helvetica", size=14)
    pdf_temp.set_xy(50, 150)
    pdf_temp.cell(110, 50, f"Documento: {documento}", align="C")
    
    pdf_temp.set_font("Helvetica", size=22)
    pdf_temp.set_xy(50, 130)
    pdf_temp.cell(110, 50, f"Curso: {curso}", align="C")

    # Guardar el PDF
    output_pdf = "certificado_completo.pdf"
    pdf_temp.output(output_pdf)

    # Enviar el archivo generado al cliente
    return send_file(output_pdf, as_attachment=True)





# Almacenar la contraseña en hash (esto solo se hace una vez)
# En un entorno de producción, esta clave debería ser almacenada en un archivo seguro o variable de entorno
hashed_password = "scrypt:32768:8:1$fhdbMkNlqdWlknv8$8ceb8ceb2c2ea43d3d83e5f7e8eadfc3fa6ffc26925ed4eec4a4713db685ac27e1baa908a1de1853ca35d09414897d04a6ca246ad33c4c0b692fb84dfcff7b96"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form["password"]

        # Verificar si la contraseña es correcta usando el hash
        if check_password_hash(hashed_password, password):
            session["authenticated"] = True  # Guardar sesión
            return redirect(url_for("menu"))  # Redirigir a la página de menú

        else:
            flash("Contraseña incorrecta", "error")  # Mensaje de error si la contraseña es incorrecta

    return render_template("login.html")









# Ruta para registrar usuarios (protegida con contraseña)
@app.route("/registrar", methods=["GET", "POST"])
def registrar_usuario():
    cursos = ["Curso de Caligrafía", "Curso de Moda", "Confección", "Marketing Digital", "Diseño Gráfico"]

    # Verificar si la sesión está autenticada
    if not session.get("authenticated"):
        return redirect(url_for("login"))  # Redirigir al login si no está autenticado

    if request.method == "POST":
        nombre = request.form["nombre"]
        documento = request.form["documento"]
        curso = request.form["curso"]

        # Validación básica
        if not nombre or not documento.isdigit() or not curso:
            return "Todos los campos son obligatorios y el documento debe ser numérico."

        # Conectar a la base de datos y verificar si el documento ya existe
        connection = conectar_bd()
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM aprobados WHERE documento = ?", (documento,))
        existing_record = cursor.fetchone()

        if existing_record:
            connection.close()
            mensaje = "El documento ya está registrado."
            return render_template("registro.html", mensaje=mensaje, cursos=cursos)

        # Si el documento no existe, proceder con la inserción
        try:
            cursor.execute(
                "INSERT INTO aprobados (nombre, documento, curso) VALUES (?, ?, ?)",  # Corregido aquí
                (nombre, documento, curso),
            )
            connection.commit()
            mensaje = "Usuario registrado con éxito."
        except sqlite3.IntegrityError:
            mensaje = "Hubo un error al registrar el usuario."
        finally:
            connection.close()

        return render_template("registro.html", mensaje=mensaje, cursos=cursos)

    return render_template("registro.html", cursos=cursos)






if not os.path.exists('uploads'):
    os.makedirs('uploads')




# Home menu administrador

@app.route("/menu")
def menu():
    # Verificar si la sesión está autenticada
    if not session.get("authenticated"):
        return redirect(url_for("login"))
    return render_template("menu.html")








# Ruta para la carga masiva
@app.route('/carga_masiva', methods=['GET', 'POST'])
def carga_masiva():
    # Verificar si la sesión está autenticada
    if not session.get("authenticated"):
        return redirect(url_for("login"))
    
    duplicados = []  # Lista para almacenar documentos duplicados
    preview_data = []  # Lista para almacenar datos de vista previa

    if request.method == 'POST':
        archivo = request.files['archivo']
        
        if archivo and archivo.filename.endswith('.csv'):
            # Guardar el archivo en el directorio 'uploads'
            archivo_path = os.path.join('uploads', archivo.filename)
            archivo.save(archivo_path)

            try:
                with open(archivo_path, newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    headers = next(reader)  # Leer encabezados

                    # Validar encabezados esperados
                    if headers != ["nombre", "documento", "curso", "fecha"]:
                        flash("El archivo no tiene el formato esperado.", "danger")
                        return redirect(url_for('carga_masiva'))

                    # Leer las filas y preparar vista previa
                    preview_data = [row for row in reader]

                    # Si el botón es "Vista previa"
                    if request.form.get("vista_previa"):
                        os.remove(archivo_path)  # Eliminar el archivo
                        return render_template('carga_masiva.html', preview_data=preview_data, headers=headers)

                    # Si el botón es "Cargar"
                    for row in preview_data:
                        row = [value.strip() for value in row]
                        if len(row) == 4:
                            nombre, documento, curso, fecha = row

                            # Verificar si el documento ya existe en la base de datos
                            connection = conectar_bd()
                            cursor = connection.cursor()
                            cursor.execute("SELECT * FROM aprobados WHERE documento = ?", (documento,))
                            registro_existente = cursor.fetchone()

                            if registro_existente:
                                duplicados.append(row)
                            else:
                                cursor.execute(
                                    "INSERT INTO aprobados (nombre, documento, curso, fecha) VALUES (?, ?, ?, ?)",
                                    (nombre, documento, curso, fecha)
                                )
                                connection.commit()
                            connection.close()
                        else:
                            print("Fila no válida:", row)

            except Exception as e:
                flash(f"Error procesando el archivo: {e}", "danger")
                return redirect(url_for('carga_masiva'))
            
            os.remove(archivo_path)  # Eliminar el archivo cargado

            if duplicados:
                flash(f"{len(duplicados)} registros duplicados encontrados. No fueron insertados.", "warning")
            else:
                flash("Carga exitosa de los registros.", "success")
            return redirect(url_for('ver_registros'))
        else:
            flash("El archivo cargado no es un CSV válido.", "danger")
            return redirect(url_for('carga_masiva'))
    
    return render_template('carga_masiva.html')



#descargar ejemplo csv
@app.route('/descargar_ejemplo')
def descargar_ejemplo():
    ejemplo_path = os.path.join('static', 'ejemplo.csv')  # Ruta al archivo de ejemplo
    return send_file(ejemplo_path, as_attachment=True)


# Función para insertar los datos en la base de datos
def agregar_a_base_datos(nombre, documento, curso, fecha):
    connection = sqlite3.connect('main.db')  # Cambiar a tu base de datos
    cursor = connection.cursor()
    
    # Verificar si la fecha es válida (por ejemplo, si está en el formato esperado)
    try:
        datetime.strptime(fecha, "%d/%m/%Y")
    except ValueError:
        raise ValueError("La fecha tiene un formato inválido.")
    
    # Suponiendo que tienes una tabla llamada 'aprobados' con las columnas adecuadas
    cursor.execute('''
        INSERT INTO aprobados (nombre, documento, curso, fecha)
        VALUES (?, ?, ?, ?)
    ''', (nombre, documento, curso, fecha))
    
    connection.commit()
    connection.close()







# ruta para ver registros

@app.route("/ver_registros", methods=["GET"])
def ver_registros():
    # Parámetros de búsqueda y paginación
    search = request.args.get('search')  # Término de búsqueda
    pagina = request.args.get('pagina', 1, type=int)  # Página actual (por defecto 1)
    registros_por_pagina = 10  # Cantidad de registros por página

    # Conectar a la base de datos
    connection = conectar_bd()
    cursor = connection.cursor()

    # Construir la consulta base
    query_base = "SELECT id, nombre, documento, curso, fecha, descargado FROM aprobados"
    query_filtro = ""
    parametros = []

    # Si hay un término de búsqueda, añadir el filtro
    if search:
        query_filtro = " WHERE nombre LIKE ? OR documento LIKE ?"
        parametros.extend(['%' + search + '%', '%' + search + '%'])

    # Contar el total de registros para la paginación
    cursor.execute(f"SELECT COUNT(*) FROM aprobados{query_filtro}", parametros)
    total_registros = cursor.fetchone()[0]
    total_paginas = (total_registros + registros_por_pagina - 1) // registros_por_pagina  # Redondeo hacia arriba

    # Calcular el offset para la paginación
    offset = (pagina - 1) * registros_por_pagina

    # Obtener los registros con límite y offset
    query_final = f"{query_base}{query_filtro} LIMIT ? OFFSET ?"
    parametros.extend([registros_por_pagina, offset])
    cursor.execute(query_final, parametros)
    registros = cursor.fetchall()

    connection.close()

    # Renderizar la plantilla con los datos necesarios
    return render_template(
        "ver_registros.html",
        registros=registros,
        search=search,
        pagina=pagina,
        total_paginas=total_paginas
    )


# Ruta para actualizar registros
@app.route("/actualizar", methods=["POST"])
def actualizar_registro():
    data = request.get_json()
    id = data["id"]
    column = data["column"]
    value = data["value"]

    # Validar que la columna sea válida
    if column not in ["nombre", "documento", "curso"]:
        return "Columna no válida", 400

    # Conectar a la base de datos y actualizar el registro
    connection = conectar_bd()
    cursor = connection.cursor()
    cursor.execute(f"UPDATE aprobados SET {column} = ? WHERE id = ?", (value, id))
    connection.commit()
    connection.close()

    return "OK", 200






#exportar a csv
@app.route("/exportar_csv", methods=["GET", "POST"])
def exportar_csv():
    if request.method == "POST":
        # Conectar a la base de datos y obtener todos los registros
        connection = conectar_bd()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM aprobados")
        registros = cursor.fetchall()
        connection.close()

        # Definir el nombre del archivo CSV que se generará
        csv_filename = "registros.csv"

        # Crear el archivo CSV en memoria
        with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Nombre", "Documento", "Curso", "Fecha"])  # Encabezados del CSV

            # Escribir los registros en el archivo CSV
            for registro in registros:
                writer.writerow([registro["nombre"], registro["documento"], registro["curso"], registro["fecha"]])

        # Enviar el archivo CSV al usuario
        return send_file(csv_filename, as_attachment=True, download_name=csv_filename)
    return redirect(url_for("ver_registros"))








# Ruta para verificar el documento

@app.route("/verificar_documento", methods=["POST"])
def verificar_documento():
    documento = request.form.get("documento")

    # Conectar a la base de datos y verificar el registro
    connection = conectar_bd()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM aprobados WHERE documento = ?", (documento,))
    registro = cursor.fetchone()
    connection.close()

    if registro:
        # Redirigir a la página de felicitaciones pasando el documento
        nombre = registro["nombre"]
        return render_template("felicitaciones.html", documento=documento, nombre=nombre )
    else:
        # Mostrar un mensaje si no cumple
        flash("El documento no está registrado o no cumplió con los requisitos del curso.", "error")
        return redirect(url_for("index"))













#editar registros 

@app.route("/eliminar/<int:id>", methods=["POST"])
def eliminar_registro(id):
    # Conectar a la base de datos y eliminar el registro con el ID especificado
    connection = conectar_bd()
    cursor = connection.cursor()
    cursor.execute("DELETE FROM aprobados WHERE id = ?", (id,))
    connection.commit()
    connection.close()

    # Redirigir a la página de registros
    flash("Registro eliminado con éxito.", "success")
    return redirect(url_for("ver_registros"))  # O usar `window.location.reload()` en el frontend






if __name__ == "__main__":
    app.run(debug=True)