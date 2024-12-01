import sqlite3

from flask import Flask, render_template, request, send_file, redirect, url_for, session, flash
from fpdf import FPDF
from datetime import datetime
from PIL import Image




app = Flask(__name__)

# Configuración de la clave secreta para sesiones
app.secret_key = "mi_clave_secreta"

# Función para conectar con la base de datos
def conectar_bd():
    connection = sqlite3.connect("certificados.db")
    connection.row_factory = sqlite3.Row  # Para usar nombres de columnas en las filas
    return connection

# Ruta principal: muestra el formulario
@app.route("/")
def index():
    return render_template("certificado.html")

# Ruta para generar el certificado
@app.route("/generar", methods=["POST"])
def generar_certificado():
    documento = request.form["documento"]

    # Conectar a la base de datos y obtener los datos
    connection = conectar_bd()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM aprobados WHERE documento = ?", (documento,))
    registro = cursor.fetchone()
    connection.close()

    if not registro:
        return render_template("error.html")

    nombre = registro["nombre"]
    curso = registro["curso"]
    fecha_aprobacion = datetime.now().strftime("%d/%m/%Y")

    # Cargar la plantilla como imagen
    template_image_path = "static/plantilla_certificado.jpg"  # O usa .png si es el caso
    img = Image.open(template_image_path)

    # Convertir la imagen a PDF (esto creará un PDF con la imagen de fondo)
    pdf_temp = FPDF()
    pdf_temp.add_page()
    
    # Convertir las dimensiones de la imagen a mm (suponiendo 72 DPI)
    img_width, img_height = img.size
    img_width_mm = img_width / 72 * 25.4
    img_height_mm = img_height / 72 * 25.4

    # Ajusta la imagen al tamaño correcto
    pdf_temp.image(template_image_path, x=0, y=0, w=img_width_mm, h=img_height_mm)


    # Usar FPDF para agregar texto sobre la imagen
    # Ajusta las coordenadas según la ubicación de los espacios en la plantilla


    pdf_temp.set_font("Times", size=28)  # Fuente, tamaño 18
    pdf_temp.set_xy(50, 100)  # Ajusta las coordenadas donde aparecerá el texto
    pdf_temp.cell(110, 50, f"{nombre}", align="C")

    # Documento en tamaño pequeño
    pdf_temp.set_font("Helvetica", size=14)  # Fuente, tamaño 14
    pdf_temp.set_xy(50, 150)  # Ajusta las coordenadas donde aparecerá el texto
    pdf_temp.cell(30, 10, f"Documento: {documento}", align="C")
    
    # Curso en tamaño mediano
    pdf_temp.set_font("Helvetica", size=16)  # Fuente, tamaño 16
    pdf_temp.set_xy(50, 100)  # Ajusta las coordenadas donde aparecerá el texto
    pdf_temp.cell(40, 10, f"Curso: {curso}", align="C")

    # Fecha en tamaño pequeño
    pdf_temp.set_font("Helvetica", size=14)  # Fuente, tamaño 14
    pdf_temp.set_xy(50, 100)  # Ajusta las coordenadas donde aparecerá el texto
    pdf_temp.cell(120, 10, f"Fecha: {fecha_aprobacion}", align="C")

    # Guardar el PDF final con la imagen como plantilla y los datos
    output_pdf = "certificado_completo.pdf"
    pdf_temp.output(output_pdf)

    # Enviar el PDF generado al cliente
    return send_file(output_pdf, as_attachment=True)







# Ruta de login (protege el acceso con una contraseña)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form["password"]

        # Verificar si la contraseña es correcta
        if password == "clave1234":  # Cambia esto por tu contraseña
            session["authenticated"] = True  # Guardar sesión
            return redirect(url_for("registrar_usuario"))  # Redirigir a la página de registro

        else:
            flash("Contraseña incorrecta", "error")  # Mensaje de error si la contraseña es incorrecta

    return render_template("login.html")

# Ruta para registrar usuarios (protegida con contraseña)
@app.route("/registrar", methods=["GET", "POST"])
def registrar_usuario():
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

        # Conectar a la base de datos e insertar datos
        connection = conectar_bd()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "INSERT INTO aprobados (nombre, documento, curso) VALUES (?, ?, ?)",
                (nombre, documento, curso),
            )
            connection.commit()
            mensaje = "Usuario registrado con éxito."
        except sqlite3.IntegrityError:
            mensaje = "El documento ya está registrado."
        finally:
            connection.close()

        return render_template("registro.html", mensaje=mensaje)

    return render_template("registro.html")

if __name__ == "__main__":
    app.run(debug=True)
