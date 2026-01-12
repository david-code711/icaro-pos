from flask import Flask, render_template, request, redirect, session, url_for
import pandas as pd
import os, markdown

app = Flask(__name__)

FILE = "inventario.xlsx"

def load_db():
    if os.path.exists(FILE):
        return pd.read_excel(FILE)
    else:
        df = pd.DataFrame(columns=["Barcode", "Name", "Price"])
        df.to_excel(FILE, index=False)
        return df

def save_db(df):
    df.to_excel(FILE, index=False)
#=========LOGIN=================
ADMIN_USER = "admin"
ADMIN_PASS = "1234"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        clave = request.form["clave"]

        if usuario == ADMIN_USER and clave == ADMIN_PASS:
            session["usuario"] = usuario
            return redirect(url_for("home"))

        return render_template("login.html", error="Usuario o contraseña incorrectos")

    return render_template("login.html")

def login_requerido(func):
    def wrapper(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

#==============================

@app.route("/", methods=["GET", "POST"])
@login_requerido
def home():
    df = load_db()

    # -------------------------
    # BUSCADOR RÁPIDO
    # -------------------------
    query = ""
    resultados = []

    if request.method == "POST":
        query = request.form["query"].lower().strip()
        resultados = df[
            df["Name"].str.lower().str.contains(query, na=False) |
            df["Barcode"].astype(str).str.contains(query)
        ][["Barcode", "Name", "Price"]].to_dict(orient="records")

    # -------------------------
    # RESUMEN DE VENTAS
    # -------------------------
    ventas_hoy = 0
    num_ventas = 0
    ticket_medio = 0

    if os.path.exists("ventas.xlsx"):
        v = pd.read_excel("ventas.xlsx")

        # Total vendido hoy
        ventas_hoy = v["TotalLinea"].sum()

        # Número de líneas (no tickets)
        num_ventas = len(v)

        if num_ventas > 0:
            ticket_medio = ventas_hoy / num_ventas

    # -------------------------
    # GRÁFICO (últimos 7 días)
    # -------------------------
    fechas = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    valores = [0, 0, 0, 0, 0, 0, 0]

    # (Más adelante podemos mejorar esto con fechas reales)

    return render_template(
        "home.html",
        title="Home",
        query=query,
        resultados=resultados,
        ventas_hoy=ventas_hoy,
        num_ventas=num_ventas,
        ticket_medio=ticket_medio,
        fechas=fechas,
        valores=valores
    )

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        df = load_db()
        barcode = request.form["barcode"].strip()

        # Prevent duplicates
        if barcode in df["Barcode"].astype(str).values:
            return "Error: Barcode already exists."

        name = request.form["name"].strip()
        price = float(request.form["price"])

        new_row = pd.DataFrame([{
            "Barcode": barcode,
            "Name": name,
            "Price": price
        }])

        df = pd.concat([df, new_row], ignore_index=True)
        save_db(df)
        return redirect("/")

    return render_template("add.html")

@app.route("/search", methods=["GET", "POST"])
def search():
    results = None
    if request.method == "POST":
        df = load_db()
        query = request.form["query"].lower()

        results = df[df["Name"].str.lower().str.contains(query, na=False) |
                     df["Barcode"].astype(str).str.contains(query)]

        results = results[["Barcode", "Name", "Price"]].to_dict(orient="records")

    return render_template("search.html", results=results)

@app.route("/delete/<barcode>")
def delete(barcode):
    df = load_db()
    df = df[df["Barcode"].astype(str) != barcode]
    save_db(df)
    return redirect("/")

@app.route("/modify/<barcode>", methods=["GET", "POST"])
def modify(barcode):
    df = load_db()
    product = df[df["Barcode"].astype(str) == barcode]

    if product.empty:
        return "Product not found."

    idx = product.index[0]

    if request.method == "POST":
        name = request.form["name"].strip()
        price = request.form["price"].strip()

        if name:
            df.at[idx, "Name"] = name
        if price:
            df.at[idx, "Price"] = float(price)

        save_db(df)
        return redirect("/")

    product = product[["Barcode", "Name", "Price"]].iloc[0].to_dict()
    return render_template("modify.html", product=product)

@app.route("/almacen", methods=["GET", "POST"])
def almacen():
    df = load_db()
    view = df[["Barcode", "Name", "Price"]]

    query = ""
    if request.method == "POST":
        query = request.form["query"].lower().strip()
        view = view[
            view["Name"].str.lower().str.contains(query, na=False) |
            view["Barcode"].astype(str).str.contains(query)
        ]

    return render_template("almacen.html", table=view.to_dict(orient="records"), query=query)

app.secret_key = "clave-super-segura"

@app.route("/ventas", methods=["GET", "POST"])
def ventas():
    df = load_db()

    # Inicializar carrito
    if "cart" not in session:
        session["cart"] = []

    cart = session["cart"]

    if request.method == "POST":
        barcode = request.form["barcode"].strip()

        # Buscar producto
        product = df[df["Barcode"].astype(str) == barcode]

        if not product.empty:
            product = product.iloc[0].to_dict()

            # Añadir al carrito
            cart.append({
                "Barcode": product["Barcode"],
                "Name": product["Name"],
                "Price": product["Price"],
                "Qty": 1
            })

            session["cart"] = cart

    # Calcular total
    total = sum(item["Price"] * item["Qty"] for item in cart)

    return render_template("ventas.html", cart=cart, total=total)

#======VENTAS========
@app.route("/ventas/add_qty/<barcode>")
def add_qty(barcode):
    cart = session.get("cart", [])
    for item in cart:
        if item["Barcode"] == barcode:
            item["Qty"] += 1
            break
    session["cart"] = cart
    return redirect("/ventas")

@app.route("/ventas/sub_qty/<barcode>")
def sub_qty(barcode):
    cart = session.get("cart", [])
    for item in cart:
        if item["Barcode"] == barcode:
            item["Qty"] -= 1
            if item["Qty"] <= 0:
                cart.remove(item)
            break
    session["cart"] = cart
    return redirect("/ventas")

@app.route("/ventas/remove/<barcode>")
def remove_item(barcode):
    cart = session.get("cart", [])
    cart = [item for item in cart if item["Barcode"] != barcode]
    session["cart"] = cart
    return redirect("/ventas")

@app.route("/ventas/change_price/<barcode>", methods=["GET", "POST"])
def change_price(barcode):
    cart = session.get("cart", [])

    # Buscar producto en el carrito
    for item in cart:
        if item["Barcode"] == barcode:
            product = item
            break
    else:
        return redirect("/ventas")

    if request.method == "POST":
        new_price = request.form["price"].strip()
        try:
            product["Price"] = float(new_price)
        except:
            pass

        session["cart"] = cart
        return redirect("/ventas")

    return render_template("change_price.html", product=product)

#===FINALIZAR===
@app.route("/finalizar", methods=["POST"])
def finalizar():
    cart = session.get("cart", [])

    if not cart:
        return redirect("/ventas")

    # Guardar venta en Excel
    df = pd.DataFrame(cart)
    df["TotalLinea"] = df["Price"] * df["Qty"]

    if os.path.exists("ventas.xlsx"):
        old = pd.read_excel("ventas.xlsx")
        df = pd.concat([old, df], ignore_index=True)

    df.to_excel("ventas.xlsx", index=False)

    # Guardar ticket temporalmente
    session["last_ticket"] = cart

    # Vaciar carrito
    session["cart"] = []

    # Calcular total
    total = sum(item["Price"] * item["Qty"] for item in cart)

    return render_template("ticket.html", ticket=cart, total=total)

#=====ENVIO DE TICKETS====
@app.route("/enviar_ticket", methods=["GET", "POST"])
def enviar_ticket():
    ticket = session.get("last_ticket", [])

    if not ticket:
        return redirect("/ventas")

    if request.method == "POST":
        email = request.form["email"].strip()
        enviar_ticket_email(email, ticket)
        session["last_ticket"] = []
        return "Ticket enviado correctamente."

    return render_template("enviar_ticket.html")

import smtplib
from email.mime.text import MIMEText

def enviar_ticket_email(destinatario, ticket):
    # CONFIGURA TU CORREO AQUÍ
    remitente = "CORREO@gmail.com"
    contraseña = "CONTRASENA"

    # Crear texto del ticket
    texto = "TICKET DE COMPRA\n\n"
    total = 0

    for item in ticket:
        linea = f"{item['Name']} x{item['Qty']} - {item['Price']}€ c/u\n"
        texto += linea
        total += item["Price"] * item["Qty"]

    texto += f"\nTOTAL: {total}€\n"
    texto += "\nGracias por su compra."

    msg = MIMEText(texto)
    msg["Subject"] = "Ticket de compra"
    msg["From"] = remitente
    msg["To"] = destinatario

    # Enviar email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(remitente, contraseña)
        server.sendmail(remitente, destinatario, msg.as_string())

#=====CHATBOT=====
import google.genai as genai
GEMINI_API_KEY = "AIzaSyDzqH5kNrAwiq_kTb7OY3BOrdzB5yUSozM"
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

#genai.configure(api_key="AIzaSyAPXilkwTb7O5D_OogFcRA85sg1EUqJ6aU")
#model = genai.GenerativeModel("gemini-2.5-flash")

from flask import session, request, render_template

@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "messages" not in session:
        session["messages"] = []

    if request.method == "POST":
        user_msg = request.form["message"]

        # Guardar mensaje del usuario
        session["messages"].append({"role": "Usuario", "content": user_msg})

        # Llamada a Gemini
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_msg
        )

        bot_reply = markdown.markdown(response.text)

        # Guardar respuesta
        session["messages"].append({"role": "ÍCAROS", "content": bot_reply})

    return render_template("chat.html", messages=session["messages"])

#=====EMPRESA======
@app.route("/empresa")
def empresa():
    return render_template("empresa.html")

if __name__ == "__main__":
    app.run(debug=True)
