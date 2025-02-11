from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import random
import string
import hashlib
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ssl
import logging

# Flask-app en logging instellen
app = Flask(__name__)
app.secret_key = 'db67f177f368400fad80606952435cad93f2a916502c7331f52fde6316d9dfda'

# Logging instellen
logging.basicConfig(level=logging.DEBUG)

# Configuratie
credentialsfile = "credentials.json"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Google Sheets setup
creds = ServiceAccountCredentials.from_json_keyfile_name(credentialsfile, scope)
client = gspread.authorize(creds)
sheet = client.open("ValentijnKaarten").sheet1

# Functie voor unieke order ID
def generate_unique_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

# E-mail configuratie
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 465
SENDER_EMAIL = "valentijnskaarten0@gmail.com"  # Vul je eigen Gmail adres in
SENDER_PASSWORD = "lklarntdvwmktgmj"  # Vul je wachtwoord in, overweeg om een App-specifiek wachtwoord te gebruiken voor veiligheid

# Functie voor het versturen van een e-mail
def send_email(to_email, subject, body):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject

    # Voeg de body toe aan de e-mail
    msg.attach(MIMEText(body, 'plain'))

    # Maak verbinding met de server en stuur de e-mail
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/order', methods=['GET', 'POST'])
def order():
    if request.method == 'POST':
        # Controleer of de gebruiker akkoord is gegaan met de voorwaarden
        if not request.form.get('accept_terms'):
            return "Je moet akkoord gaan met de algemene voorwaarden."

        # Bestelling verwerken
        order_id = generate_unique_id()
        email = request.form['email']
        email_receiver = request.form['email_receiver']
        name_from = request.form['name_from']
        name_to = request.form['name_to']
        klas = request.form['klas']
        message = request.form['message']
        anonim = request.form.get('anonim', 'nee')
        card_type = request.form['card_type']
        lolly = request.form.get('lolly', 'nee')
        balloon = request.form.get('balloon', 'nee')
        card_own_text = request.form.get('card_own_text', 'nee')
        card = request.form.get('card', 'nee')
        digital_card = 'ja'

        # Prijsberekening
        total_price = 0
        if lolly == 'ja':
            total_price += 1
        if balloon == 'ja':
            total_price += 1
        if card_own_text == 'ja':
            total_price += 0.5
        if card == 'ja':
            total_price += 0.5

        paid = 'ja' if total_price == 0 else 'nee'

        formatted_price = f"{total_price:.2f}".replace('.', ',')

        # Voeg bestelling toe aan Google Sheets
        sheet.append_row([email, email_receiver, name_from, name_to, klas, message, card_type, anonim, lolly, balloon, card_own_text, card, digital_card, paid, order_id, formatted_price])

        # Sla order gegevens op in sessie
        session['order_id'] = order_id
        session['card_type'] = card_type
        session['message'] = message
        session['total_price'] = formatted_price if total_price > 0 else 'Gratis'
        
        # Stuur een bevestigingsemail naar de klant
        subject = "Info van je Valentijnskaart bestelling"
        body = f"Beste {name_from},\n\nBedankt voor je bestelling van een Valentijnskaart!\n\nBestelnummer: {order_id}\nTotale prijs: €{formatted_price}\n\nMet vriendelijke groet,\nKries Prahladsingh.\n\nDit is een Automatische Email."
        send_email(email, subject, body)

        return redirect(url_for('confirmation'))
    
    return render_template('order.html')

@app.route('/confirmation')
def confirmation():
    order_id = session.get('order_id', '')
    card_type = session.get('card_type', '')
    message = session.get('message', '')
    total_price = session.get('total_price', '')

    return render_template('confirmation.html', order_id=order_id, card_type=card_type, message=message, total_price=total_price)

@app.route('/activate', methods=['GET'])
def activate():
    order_id = request.args.get('id', '').strip()

    if not order_id:
        logging.warning("Geen ID opgegeven bij activatie")
        return jsonify({"error": "Geen ID opgegeven!"}), 400

    try:
        records = sheet.get_all_records()
        logging.debug(f"Records opgehaald: {records}")

        for i, row in enumerate(records, start=2):  
            if str(row.get("ID")) == order_id:
                if row.get("Betaald") == "nee":
                    sheet.update_cell(i, 14, "ja")  # Update 'Betaald' kolom (kolom 14)
                    logging.info(f"Bestelling {order_id} geactiveerd")
                    return jsonify({"message": f"Bestelling {order_id} geactiveerd!"}), 200
                logging.info(f"Bestelling {order_id} was al geactiveerd")
                return jsonify({"message": f"Bestelling {order_id} was al geactiveerd!"}), 200

        logging.warning(f"Bestelling {order_id} niet gevonden")
        return jsonify({"error": f"Bestelling {order_id} niet gevonden!"}), 404

    except Exception as e:
        logging.error(f"Fout bij activatie van {order_id}: {str(e)}")
        return jsonify({"error": f"Fout bij activatie: {str(e)}"}), 500


@app.route('/delete', methods=['GET'])
def delete_order():
    order_id = request.args.get("id", "").strip()
    reden = request.args.get("reden", "").strip()

    if not order_id:
        logging.warning("Geen ID opgegeven bij verwijderen")
        return jsonify({"error": "ID is vereist"}), 400

    try:
        records = sheet.get_all_records()
        logging.debug(f"Records opgehaald voor verwijderen: {records}")

        row_to_delete = None
        name_from = None
        email = None

        # Find the row to delete
        for i, row in enumerate(records, start=2):
            if str(row.get("ID")) == order_id:
                row_to_delete = i
                name_from = row.get("NameVan")
                email = row.get("Email")
                break

        if not row_to_delete:
            logging.warning(f"Bestelling {order_id} niet gevonden bij verwijderen")
            return jsonify({"error": f"Bestelling {order_id} niet gevonden!"}), 404

        # Construct the email body
        subject = f"Verwijdering bestelling {order_id}"
        body = f"Beste {name_from},\n\nJe bestelling van een Valentijnskaart!\n\nBestelnummer: {order_id}\nIs verwijderd\n"
        if reden:
            body += f"\nReden van verwijdering:\n{reden}\n"
        body += "\nMet vriendelijke groet,\nKries Prahladsingh.\n\nDit is een Automatische Email."

        # Send the email
        send_email(email, subject, body)

        # Delete the row from the sheet
        sheet.delete_rows(row_to_delete)
        logging.info(f"Bestelling {order_id} verwijderd")
        return jsonify({"message": f"Bestelling {order_id} verwijderd!"}), 200

    except Exception as e:
        logging.error(f"Fout bij verwijderen van {order_id}: {str(e)}")
        return jsonify({"error": f"Fout bij verwijderen: {str(e)}"}), 500

@app.route('/orders', methods=['GET'])
def get_orders():
    try:
        records = sheet.get_all_records()
        logging.debug(f"Alle bestellingen opgehaald: {records}")
        return jsonify({"orders": records}), 200
    except Exception as e:
        logging.error(f"Fout bij ophalen bestellingen: {str(e)}")
        return jsonify({"error": f"Fout bij ophalen bestellingen: {str(e)}"}), 500

@app.route('/voorwaarden')
def voorwaarden():
    return render_template('voorwaarden.html')

@app.route('/info')
def info():
    return render_template('info.html')

@app.route('/hoi')
def hallo
    return "Hallo :)"


# Random Secret secure String Generator
def generate_random_string(length):
    """Generate a random string of letters and numbers of the specified length."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choices(characters, k=length))

def hash_string_sha256(input_string):
    """Hash the input string using SHA-256."""
    sha256_hash = hashlib.sha256(input_string.encode()).hexdigest()
    return sha256_hash

def hash_string_sha512(input_string):
    """Hash the input string using SHA-512."""
    sha512_hash = hashlib.sha512(input_string.encode()).hexdigest()
    return sha512_hash

@app.route('/rand', methods=['GET'])
def generate_and_encrypt():
    # Get the 'length' parameter from the query string, default to 256 if not provided
    length = request.args.get('length', default=256, type=int)

    # Validate the length parameter
    if length <= 0:
        return jsonify({"error": "Length must be a positive integer"}), 400

    # Step 1: Generate a random string of the specified length
    random_string = generate_random_string(length)

    # Step 2: Encode the string in Base64
    base64_encoded = base64.b64encode(random_string.encode()).decode()

    # Step 3: Hash the string using SHA-256 and SHA-512
    sha256_hashed = hash_string_sha256(random_string)
    sha512_hashed = hash_string_sha512(random_string)

    # Step 4: Return the results as JSON
    return jsonify({
        "random_string": random_string,
        "base64_encoded": base64_encoded,
        "sha256_hashed": sha256_hashed,
        "sha512_hashed": sha512_hashed
    })


# Funny Stuff
# Replace this with your actual Pastebin URL
GITHUB_URL = 'https://raw.githubusercontent.com/m801698/flask/refs/heads/main/bibiel.txt'

@app.route('/funny', methods=['GET'])
def funny():
    # Fetch the content from Pastebin
    response = requests.get(GITHUB_URL)
    
    if response.status_code == 200:
        paste_content = response.text
    else:
        paste_content = "Error."

    # HTML template with embedded CSS
    html_template = '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="/static/index.css">
        <title>Fummy</title>
    </head>
    <body>
        <h1>Funny Stuff</h1>
        <pre>{{ content }}</pre>
    </body>
    </html>
    '''

    return render_template_string(html_template, content=paste_content)

if __name__ == '__main__':
    app.run(debug=True)
