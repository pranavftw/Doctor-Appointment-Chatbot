
from queue import Full
import time
from flask_cors import cross_origin  # Import CORS
from flask import Flask, request, jsonify
import requests
import google.generativeai as genai
import os
import pytesseract
from PIL import Image
import PyPDF2
import pdfplumber
import spacy
import firebase_admin
from firebase_admin import credentials, db
import jwt
import datetime
from flask_cors import CORS
from googletrans import Translator
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import base64

translator = Translator()

app = Flask(__name__)
cors=CORS(app)


GOOGLE_API_KEY = ''
GOOGLE_CSE_ID = ''

SECRET_KEY = "1234" 


cred = credentials.Certificate(r"")
firebase_admin.initialize_app(cred, {
    'databaseURL': ''
})


# OpenFDA API Base URL
OPENFDA_BASE_URL = "https://api.fda.gov/drug/label.json"

pytesseract.pytesseract.tesseract_cmd = r'D:\PP12\tessocr\tesseract.exe'

# Configure Google Gemini API
genai.configure(api_key="")

# Configure upload folder and file size limits
UPLOAD_FOLDER = "./uploads"
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2MB

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load NLP Model
nlp = spacy.load("en_core_web_sm")


# API endpoint to handle login and store data in Firebase
@app.route("/boot/login", methods=["POST"])
@cross_origin("*")
def login():
    try:
        # Get name, email, and password from the JSON body
        data = request.get_json()
        name = data.get("name")
        email = data.get("email")
        password = data.get("password")

        if not name or not email or not password:
            return jsonify({"error": "All parameters are required!"}), 400

        # Reference to the Firebase Realtime Database
        users_ref = db.reference("users")

        # Query the database to check if an email already exists
        query = users_ref.order_by_child("email").equal_to(email).get()

        if query:  # If query returns any result, the email exists
            for key, value in query.items():
                # Check if name matches as well
                if value.get("name") == name:
                    user_data = {key: value}  # Store the matched user data
                    break  # Exit loop if user is found
                else:
                    user_data = None  # If name doesn't match, reset user_data
        else:
            user_data = None  # If email doesn't exist, set user_data to None

        if user_data:
            # User already exists, get their details
            user_id = list(user_data.keys())[0]  # Get user ID from Firebase
            user_details = list(user_data.values())[0]  # Get user details
            user_name = user_details["name"]
            user_email = user_details["email"]

            # Generate JWT token
            token = jwt.encode({
                "user_id": user_id,
                "email": user_email,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)  # Token expiration (8 hours)
            }, SECRET_KEY, algorithm="HS256")

            # Ensure folder exists or update it if necessary
            user_folder = os.path.join("presp", user_id)
            os.makedirs(user_folder, exist_ok=True)  # Create or update the folder

            return jsonify({
                "message": "User email and name validated successfully! Login successful.",
                "email": user_email,
                "name": user_name,
                "password": password,
                "user_id": user_id,
                "TOKEN": token
            })
        
        # User does not exist or name doesn't match the email, create a new one
        new_user_ref = users_ref.push({
            "name": name,
            "email": email,
            "password": password,
            "cart": 0
        })
        if "cart" not in new_user_ref.get():
            new_user_ref.update({"cart": {}})  # Ensure the cart field is created if not already

        user_id = new_user_ref.key

        # Generate JWT token for the new user
        token = jwt.encode({
            "user_id": user_id,
            "email": email,
            "password": password,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)  # Token expiration (8 hours)
        }, SECRET_KEY, algorithm="HS256")

        # Ensure folder exists for the new user
        user_folder = os.path.join("presp", user_id)
        os.makedirs(user_folder, exist_ok=True)  # Create or update the folder

        return jsonify({
            "message": "User created successfully!",
            "user_id": user_id,
            "email": email,
            "name": name,
            "password": password,
            "TOKEN": token
        })

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

    
   
# API endpoint to handle signin and read data in Firebase
@app.route("/boot/signin", methods=["POST"])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def signin():
    try:
        # Get name and email from the JSON body
        data = request.get_json()
        name = data.get("name")
        password = data.get("password")
        print("NAME GOT FROM FRONTEND",name)
        print("PASSWORD GOT FROM FRONTEND SIGN IN",password)

        if not name or not password:
            return jsonify({"error": "All parametrs are required!"}), 400

        # Reference to the Firebase Realtime Database
        users_ref = db.reference("users")

        # Check if the user already exists
        user_data2 = users_ref.order_by_child("name").equal_to(name).get()
        print("CHECK THIS NAME",user_data2)
        user_data = users_ref.order_by_child("password").equal_to(password).get()
        
        
        if user_data and user_data2:
            # User already exists, get their details
            user_id = list(user_data2.keys())[0]  # Get user ID from Firebase
            user_details = list(user_data2.values())[0]  # Get user details
            user_name = user_details["name"]
            print("SIGN IN NAME VALIDATED = ",user_name)
            user_email = user_details["email"]
            print("SIGN IN EMAIL VALIDATED = ",user_email)
            user_password = user_details["password"]
            print("SIGN IN PASSWORD VALIDATED = ",user_password)

            # Generate JWT token
            token = jwt.encode({
                "user_id": user_id,
                "email": user_email,
                "password": user_password,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8)  # Token expiration (8 hours)
            }, SECRET_KEY, algorithm="HS256")
            user_folder = os.path.join("presp", user_id)
            os.makedirs(user_folder, exist_ok=True)  # Create or update the folder

            return jsonify({
                "message": "User exists and validated",
                "email": user_email,
                "name": user_name,
                "password": user_password,
                "user_id": user_id,
                "TOKEN": token
            })
    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    






@app.route('/boot/addcart', methods=['POST'])
@cross_origin("*")
def add_to_cart():
    try:
        # Step 1: Get user ID from request (e.g., passed from frontend)
        user_id,email=verify_token()
        if not user_id:
            print("JWT TOKEN ERROR")
            return jsonify({"error": "JWT token is invalid or expired. Please log in again."}), 403
        print("JWT VERIFIED user id from add to cart is",user_id)
        product_name = request.json.get('name')
        product_price = request.json.get('price')
        product_quantity = request.json.get('quantity')
       # user_id = "-OH81oNdCEDC1Bk39ILS"
        # Ensure price is a float and quantity is an integer
        try:
            product_price = float(product_price)  # Convert price to float
            print("PRODUCT PRICE:", product_price)
            product_quantity = int(product_quantity)  # Convert quantity to integer
            print("Quantity:", product_quantity)
            y = product_quantity * product_price
            print("Total for the item:", y)
        except ValueError:
            return jsonify({"message": "Invalid price or quantity", "status": "error"}), 400

        if not user_id or not product_name or not product_price or not product_quantity:
            return jsonify({"message": "Missing data in request", "status": "error"}), 400

        # Step 2: Get reference to Firebase cart for this user
        cart_ref = db.reference(f"users/{user_id}/cart")

        # Step 3: Check if the product is already in the cart
        product_ref = cart_ref.child(product_name)  # Using product name as key (you can use product_id)

        existing_product = product_ref.get()  # Get the existing product if it exists

        if existing_product:
            # Product exists, update the quantity
            new_quantity = existing_product['quantity'] + product_quantity
            product_ref.update({'quantity': new_quantity})
        else:
            # Product does not exist, create a new entry
            product_ref.set({
                'name': product_name,
                'price': product_price,
                'quantity': product_quantity
            })

        # Step 4: Calculate the total price by summing up all items in the cart
        cart_items = cart_ref.get()  # Get all items in the cart
        if not cart_items:
            return jsonify({"message": "Cart is empty", "total_price": "₹0.00"}), 200  # Early return for empty cart

        total_price = 0  # Initialize total price to 0

        # Calculate total cost by summing up price * quantity for each item
        for item in cart_items.values():
            if 'price' in item and 'quantity' in item:
                total_price += item['price'] * item['quantity']
            else:
                return jsonify({"message": "Error in cart item data", "status": "error"}), 400

        # Ensure total price is a float for correct formatting
        total_price = float(total_price)

        # Update total price in Firebase
        db.reference(f"users/{user_id}/total_price").set(total_price)

        # Return the response with formatted total price
        return jsonify({"message": "Product added to cart successfully!", "total_price": f"₹{total_price:.2f}"})

    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500


@app.route('/boot/retrievecart', methods=['POST'])
@cross_origin("*")
def retrieve_cart():
    try:
        # Step 1: Get user ID from request body
        #data = request.get_json()
        # user_id = data.get('user_id')
        #user_id = "-OH81oNdCEDC1Bk39ILS"
        user_id,email=verify_token()
        print("USER ID FROM retrieve cart VERIFY TOKEN IS",user_id,"EMAIL IS ",email)
        if not user_id:
            print("JWT TOKEN ERROR")
            return jsonify({"error": "JWT token is invalid or expired. Please log in again."}), 403
        print("JWT VERIFIED user id from retrieve cart is",user_id)
       
        print("RETRIEVE CART USER ID", user_id)
        if not user_id:
            return jsonify({"message": "User ID is required", "status": "error"}), 400

        # Step 2: Get reference to Firebase cart for this user
        cart_ref = db.reference(f"users/{user_id}/cart")
        
        # Step 3: Retrieve cart items
        cart_items = cart_ref.get()  # Get all items in the cart
        total_price = 0  # Initialize total price to 0

        # Step 4: Prepare cart data to return
        if cart_items:
            # Initialize structured product details
            product_details = {}
            product_count = 1
            
            cart_data = []  # To store original cart data for the frontend
            for item in cart_items.values():
                item_total = item['price'] * item['quantity']
                total_price += item_total
                
                # Add to the original cart data
                cart_data.append({
                    "name": item['name'],
                    "price": item['price'],
                    "quantity": item['quantity']
                })
                
                # Add to structured product details
                product_details[f"Product {product_count}"] = {
                    "Product Name": item['name'],
                    "Product Quantity": item['quantity']
                }
                product_count += 1
            
            
            # Format the total price as a float with 2 decimal places
            total_price = float(total_price)

            return jsonify({
                "message": "Cart retrieved successfully!",
                "cart_data": cart_data,  # Original cart data for frontend
                "total_price": f"₹{total_price:.2f}",
                "product_details": product_details,  # Structured product details
            
            })
        else:
            return jsonify({"message": "No items found in the cart", "status": "error"}), 404

    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500



@app.route('/boot/updatecart', methods=['POST'])
@cross_origin("*")
def update_cart():
    try:
        # Get the updated cart data from the frontend
        data = request.get_json()
        user_id,email=verify_token()
        print("USER ID FROM update cart VERIFY TOKEN IS",user_id,"EMAIL IS ",email)
        if not user_id:
            print("JWT TOKEN ERROR")
            return jsonify({"error": "JWT token is invalid or expired. Please log in again."}), 403
        print("JWT VERIFIED user id from update cart is",user_id)
       
        product_name = data.get('name')
        print(product_name)
        new_quantity = data.get('quantity')
        print(new_quantity)
        deleted = data.get('deleted')
        #product_price = data.get('price')

        # Validate data
        if not user_id or not product_name or new_quantity is None or deleted is None:
            return jsonify({"message": "Missing data in request", "status": "error"}), 400

        # Get reference to the user's cart in Firebase
        cart_ref = db.reference(f"users/{user_id}/cart")
        product_ref = cart_ref.child(product_name)

        # Check if product exists
        existing_product = product_ref.get()
        if not existing_product:
            return jsonify({"message": "Product not found in cart", "status": "error"}), 404

        # If the product needs to be deleted
        if deleted or new_quantity < 1:
            product_ref.delete()  # Delete product from cart
            return jsonify({"message": "Product removed from cart successfully", "status": "success"}), 200

        # Update the product quantity if not deleted
        product_ref.update({'quantity': new_quantity})

        # Recalculate total price
        cart_items = cart_ref.get()
        total_price = sum(item['price'] * item['quantity'] for item in cart_items.values())
        db.reference(f"users/{user_id}/total_price").set(total_price)
        print("total price dynamic updation =",total_price)

        # Return the updated total price
        return jsonify({"message": "Cart updated successfully!", "total_price": f"₹{total_price:.2f}"}), 200

    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500


@app.route('/boot/deliveryupdate', methods=['POST'])
@cross_origin("*")
def deliveryupdate():
    try:
        # Get data from frontend
        data = request.json

        # Replace with dynamic user ID fetched from session or request
        #user_id = "-OH81oNdCEDC1Bk39ILS"  # Example user ID for fallback
        user_id,email=verify_token()
        print("USER ID FROM deliveryupdate VERIFY TOKEN IS",user_id,"EMAIL IS ",email)
        if not user_id:
            print("JWT TOKEN ERROR")
            return jsonify({"error": "JWT token is invalid or expired. Please log in again."}), 403
        print("JWT VERIFIED user id from deliveryupdate is",user_id)
       
        # Generate a unique order ID (e.g., using timestamp or unique ID logic)
        order_id = f"order{int(time.time())}" # Example: order followed by a timestamp
        
        print("ORDER ID=",order_id)
        # Retrieve product details from the cart using retrievecart
        cart_response = retrieve_cart()
        cart_data = cart_response.get_json()
        
        if cart_data.get("status") == "error":
            return jsonify({"message": "Failed to retrieve cart details", "status": "error"}), 400

        # Prepare product details for Firebase
        products = {}
        for idx, item in enumerate(cart_data.get("cart_data", []), start=1):
            products[f"product{idx}"] = {
                "product name": item["name"],
                "product quantity": item["quantity"],
                "product price": item["price"]
                
            }

        # Build the order details
        order_details = {
            "delivery name": data.get("deliveryName"),
            "delivery address 1": data.get("deliveryAddress1"),
            "delivery address 2": data.get("deliveryAddress2"),
            "delivery email": data.get("deliveryEmail"),
            "phone number": data.get("phoneNumber"),
            "product details": products,
            "orderTrackLink" : "https://www.delhivery.com/tracking"
        }

        # Save order details to Firebase under the user -> orders -> orderID
        user_ref = db.reference(f'users/{user_id}/orders/{order_id}')
        user_ref.set(order_details)

        # Call paymentstatus function
        payment_status = paymentstatus()

        # Return payment status and order ID to frontend
        return jsonify({"paymentStatus": payment_status, "orderId": order_id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



# Payment Status Function(LINK WITH GPAY OR SOME EXT PAY API)
def paymentstatus():
    # Simulate payment processing
    return "Successful Payment"

@app.route('/boot/getorders', methods=['POST'])
@cross_origin("*")
def get_orders():
    try:
        # Step 1: Get user ID from request (assuming it's passed in the JWT token)
        #data = request.get_json()
        #user_id = data.get('user_id')  # Assuming user_id is passed in the body
        print("BOOM HERE ")
        user_id,email=verify_token()
        print("USER ID FROM getorders VERIFY TOKEN IS",user_id,"EMAIL IS ",email)
        if not user_id:
            print("JWT TOKEN ERROR")
            return jsonify({"error": "JWT token is invalid or expired. Please log in again."}), 403
        print("JWT VERIFIED user id from getorders is",user_id)
       
        
        if not user_id:
            return jsonify({"message": "User ID is required", "status": "error"}), 400
        
        print("Fetching orders for user ID:", user_id)
        
        # Step 2: Fetch the orders for this user from Firebase
        orders_ref = db.reference(f"users/{user_id}/orders")
        orders_data = orders_ref.get()  # Get all orders for the user
        
        if not orders_data:
            return jsonify({"message": "No orders found for this user", "status": "error"}), 404

        # Step 3: Format the orders data
        orders = []
        for order_id, order in orders_data.items():
            # Format the order details
            order_details = {
                "orderId": order_id,
                "deliveryAddress1": order.get("delivery address 1", ""),
                "deliveryAddress2": order.get("delivery address 2", ""),
                "phoneNumber": order.get("phone number", ""),
                "orderTrackLink": order.get("orderTrackLink", ""),
                "products": []
            }

            # Add the product details (if available)
            if "product details" in order:
                for product_key, product in order["product details"].items():
                    order_details["products"].append({
                        "name": product.get("product name", ""),
                        "quantity": product.get("product quantity", 1),
                        "price": product.get("product price", 0.0)
                    })
            
            # Append this order to the orders list
            orders.append(order_details)

        # Step 4: Return the formatted orders data as JSON
        return jsonify({"orders": orders, "status": "success"}), 200

    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500











    
def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF files."""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        print("pdf text extracting")
        return " ".join(page.extract_text() for page in pdf_reader.pages)
    except Exception:
        # Backup method for PDFs
        with pdfplumber.open(pdf_file) as pdf:
            return " ".join(page.extract_text() for page in pdf.pages)


def extract_text_from_image(image_file):
    """Extract text from image files using OCR."""
    print("image text extracting")
    image = Image.open(image_file)
    return pytesseract.image_to_string(image)


def extract_text_from_txt(txt_file):
    print("TXT text extracting")
    """Extract text from TXT files."""
    return txt_file.read().decode("utf-8")


def process_uploaded_file(file):
    """Determine file type and extract text."""
    if file.filename.endswith(".pdf"):
        return extract_text_from_pdf(file)
    elif file.filename.endswith((".jpg", ".jpeg", ".png")):
        return extract_text_from_image(file)
    elif file.filename.endswith(".txt"):
        return extract_text_from_txt(file)
    else:
        raise ValueError("Unsupported file format. Please upload a PDF, JPG, JPEG, PNG, or TXT file.")


def summarize_with_gemini(prompt):
    """Generate a summary using Google Gemini."""
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text.strip()

def summarize_with_gemini_ifnofda(prompt1):
    """Generate a summary using Google Gemini."""
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt1)
    return response.text.strip()


def validate_medicine_names(user_input):
    """Validate if the input contains medicine names using Google Gemini API."""
    try:
        prompt = f"Are these valid medicine names? {user_input} Respond with 'yes' or 'no'."
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip().lower() == "yes"
    except Exception:
        return False


def fetch_medicine_data(medicine_name):
    """Fetch medicine details from the OpenFDA API."""
    try:
        params = {"search": f"openfda.brand_name:{medicine_name}", "limit": 1}
        response = requests.get(OPENFDA_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("results"):
            result = data["results"][0]
            return {
                "brand_name": result.get("openfda", {}).get("brand_name", ["N/A"])[0],
                "generic_name": result.get("openfda", {}).get("generic_name", ["N/A"])[0],
                "active_ingredient": result.get("active_ingredient", ["N/A"])[0],
                "purpose": result.get("purpose", ["N/A"])[0],
                "indications": result.get("indications_and_usage", ["N/A"])[0],
                "warnings": result.get("warnings", ["N/A"])[0],
                "storage": result.get("storage_and_handling", ["N/A"])[0],
                "manufacturer": result.get("openfda", {}).get("manufacturer_name", ["N/A"])[0],
                "package": result.get("package_label_principal_display_panel", ["N/A"])[0],
            }
        return None
    except requests.RequestException:
        return None


def summarize_medicine_info(medicine_data):
    """Summarize all medicine details using Google Gemini API."""
    try:
        details = (
            f"Brand Name: {medicine_data['brand_name']}\n"
            f"Generic Name: {medicine_data['generic_name']}\n"
            f"Active Ingredient: {medicine_data['active_ingredient']}\n"
            f"Purpose: {medicine_data['purpose']}\n"
            f"Indications: {medicine_data['indications']}\n"
            f"Warnings: {medicine_data['warnings']}\n"
            f"Storage: {medicine_data['storage']}\n"
            f"Manufacturer: {medicine_data['manufacturer']}\n"
            f"Package: {medicine_data['package']}\n"
        )
        prompt = f"Summarize the following information in under 120 words, the information should be about what the medicine is and how it can help, so dont include any other irrelevant infomation and the name should be the medicine only not the brand name etc, it should be a good response:, bold whatever is important. \n\n{details}"
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return "Error in summarizing medicine details."

# Function to verify the JWT token
def verify_token():
    token = request.headers.get("Authorization")
    print("TOKEN IS = ",token)
    if not token:
        print("Token is missing from frontend")
        return None, "Token is missing!"

    try:
        # Strip 'Bearer ' prefix if present
        token = token.replace("Bearer ", "")
        # Decode the token and get the user_id and email
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded_token.get("user_id")
        print(user_id)
        email = decoded_token.get("email")
        print(email)
        if not user_id:
            return None, "Token is invalid!"
        return user_id, email
    except jwt.ExpiredSignatureError:
        
        return None, "Token has expired!"
    except jwt.InvalidTokenError:
        return None, "Invalid token!"



@app.route("/boot/upload_presp", methods=["POST"])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def upload_prescription():
    """Handle prescription file uploads and store them in user-specific folders."""
    # Verify the token and get the user_id and email
    user_id,error_message = verify_token()

    if not user_id:
        print("JWT TOKEN ERROR")
        return jsonify({"error jwt token needed": error_message}), 403  # Return 403 if token is invalid or expired

    if "file" not in request.files:
        return jsonify({"error": "File is required."}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "No file selected for upload."}), 400

    if file and allowed_file(file.filename):
        # Now we have the user_id and email from the verified JWT token
        # You can use the user_email here if needed, NOT REQUIRED FOR NOW

        # Create the user's folder in the prescriptions directory
        user_folder = os.path.join("presp", user_id)
        os.makedirs(user_folder, exist_ok=True)

        # Save the uploaded file to the user-specific folder
        file_path = os.path.join(user_folder, file.filename)
        file.save(file_path)

        # Extract text and summarize the prescription
        try:
            text = process_uploaded_file(file)
            if not text:
                file_extension = os.path.splitext(file.filename)[1]  # Extract the file extension
                print("TEXT EXTRACT ERROR")
                return jsonify({
                "error": f"No text could be extracted from the uploaded {file_extension} file. Please upload a valid prescription file."
                }), 400
            # Summarize the prescription text using Google Gemini
            prescription_summary = format_gemini_response(summarize_with_gemini(
                f"dO THIS ONLY IF THE TEXT IS A VALID PRESCRIPTION, put this prescription in points by highlighting the medicines, their dosages, and usage instructions,strictly bold the important terms if its a prescription, and keep the instructions to be taken, medicine name, and precautions in points, otherwise if the text doesn't contain any relevant information about how a medical prescription, add the line 'please upload a valid prescription.' along with a 20 word summary on uploaded text:\n\n{text}"
            ))

            return jsonify({
                "message": "File uploaded and saved successfully.",
                "file_path": file_path,
                "prescription_summary": prescription_summary
            }), 200

        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": f"Error processing the uploaded file: {str(e)}"}), 500

    return jsonify({"error": "Invalid file type or size. Allowed types: pdf, jpg, jpeg, png. Max size: 2MB."}), 400

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "File too large. Maximum allowed size is 2MB."}), 413


@app.route("/boot/logout", methods=["POST"])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def logout():
    """Handle user logout and delete the user's prescription folder."""
    # Verify the token to get the user_id
    print("logout block entered")
    user_id,email= verify_token()

    if not user_id:
        print("JWT TOKEN ERROR")
        return jsonify({"error": "JWT token is invalid or expired. Please log in again."}), 403
    print("JWT VERIFIED")
    # Define the path to the user's prescription folder
    user_folder = os.path.join("presp", user_id)
    print("Userid:",user_id)
    try:
        # Check if the folder exists
        if os.path.exists(user_folder):
            # Delete the folder and its contents
            import shutil
            shutil.rmtree(user_folder)
            print(f"Deleted folder: {user_folder}")
        else:
            print(f"No folder found for user: {user_id}")

        return jsonify({"response": "Logout successful. User data has been cleared."}), 200

    except Exception as e:
        print(f"Error during logout: {str(e)}")
        return jsonify({"response": f"Failed to log out: {str(e)}"}), 500

def detect_disease_or_symptom(user_message):
    """
    Determine if the input message is symptom or disease-related using Gemini.
    :param user_message: str - The user's input message.
    :return: bool - True if symptom or disease-related, False otherwise.
    """
    try:
        # Prompt to analyze the user's input for symptom-related information
        gemini_prompt = (
            f"Analyze the following text and respond with 'Yes' or 'No'. "
            f"Is this text related to symptoms, diseases, info on medical procedures like cpr etc or general comparison between medical terms or health related information or health conditions? Text: '{user_message}'"
        )
        # Send the prompt to Gemini
        gemini_response = summarize_with_gemini_ifnofda(gemini_prompt)

        # Process the Gemini response (assumes Gemini returns 'Yes' or 'No')
        if gemini_response.strip().lower() == "yes":
            return True
        elif gemini_response.strip().lower() == "no":
            return False
        else:
            # Log unexpected response for debugging
            print(f"Unexpected Gemini response: {gemini_response}")
            return False
    except Exception as e:
        print(f"Error in detect_disease_or_symptom: {e}")
        return False




def ultimate_thankyou(user_message):
    """
    Determine if the input message is symptom or disease-related using Gemini.
    :param user_message: str - The user's input message.
    :return: bool - True if symptom or disease-related, False otherwise.
    """
    try:
        # Prompt to analyze the user's input for symptom-related information
        gemini_prompt = (
            f"Analyze the following text and respond with 'Yes' or 'No'. "
            f"Is the word or text {user_message} is like a acknowledgemnet text like bye, or thanks a lot, or anything similar?"
        )
        # Send the prompt to Gemini
        gemini_response = summarize_with_gemini_ifnofda(gemini_prompt)

        # Process the Gemini response (assumes Gemini returns 'Yes' or 'No')
        if gemini_response.strip().lower() == "yes":
            return True
        elif gemini_response.strip().lower() == "no":
            return False
        else:
            # Log unexpected response for debugging
            print(f"Unexpected Gemini response: {gemini_response}")
            return False
    except Exception as e:
        print(f"Error in detect_disease_or_symptom: {e}")
        return False




def nutrition(user_message):
    """
    Determine if the input message is symptom or disease-related using Gemini.
    :param user_message: str - The user's input message.
    :return: bool - True if symptom or disease-related, False otherwise.
    """
    try:
        # Prompt to analyze the user's input for symptom-related information
        gemini_prompt = (
            f"Analyze the following text and respond with 'Yes' or 'No' only and not anything else. "
            f"Is the word or text {user_message} related to the user asking about a nutrition plan or diet plan or anything similar?"
        )
        # Send the prompt to Gemini
        gemini_response = summarize_with_gemini_ifnofda(gemini_prompt)

        # Process the Gemini response (assumes Gemini returns 'Yes' or 'No')
        if gemini_response.strip().lower() == "yes":
            return True
        elif gemini_response.strip().lower() == "no":
            return False
        else:
            # Log unexpected response for debugging
            print(f"Unexpected Gemini response: {gemini_response}")
            return False
    except Exception as e:
        print(f"Error in detect_disease_or_symptom: {e}")
        return False




def format_gemini_response(raw_output):
    """
    Format the raw output from Gemini for user-friendly HTML presentation.
    :param raw_output: str - The raw text output from Gemini.
    :return: str - The formatted HTML response.
    """
    import re  # Use regex to handle inline formatting
    
    try:
        # Split the raw output into lines for processing
        lines = raw_output.strip().split("\n")
        
        # Initialize an empty list to hold formatted lines
        formatted_lines = []

        # Regular expression for inline bold formatting (**text**)
        bold_pattern = r"\*\*(.*?)\*\*"

        # Iterate through each line to format it
        for line in lines:
            line = line.strip()
            if line.startswith("* "):
                # Format bullet points with <li> tags for HTML display
                bullet_text = re.sub(bold_pattern, r"<b>\1</b>", line[2:].strip())
                formatted_lines.append(f"<li>{bullet_text}</li>")
            else:
                # Handle inline bold formatting in general text
                formatted_text = re.sub(bold_pattern, r"<b>\1</b>", line)
                formatted_lines.append(f"<p>{formatted_text}</p>")

        # Join the formatted lines into a single HTML response
        formatted_response = "".join(formatted_lines)

        return formatted_response
    except Exception as e:
        print(f"Error formatting Gemini response: {e}")
        return "<p>Sorry, there was an error processing the response.</p>"


def format_gemini_response2222(raw_output):
    """
    Format the raw output from Gemini for user-friendly HTML presentation.
    :param raw_output: str - The raw text output from Gemini.
    :return: str - The formatted HTML response.
    """
    import re  # Use regex to handle inline formatting
    
    try:
        # Split the raw output into lines for processing
        lines = raw_output.strip().split("\n")
        
        # Initialize an empty list to hold formatted lines
        formatted_lines = []

        # Regular expression for inline bold formatting (**text**)
        bold_pattern = r"\*\*(.*?)\*\*"

        # Iterate through each line to format it
        for line in lines:
            line = line.strip()
            if line.startswith("* "):
                # Format bullet points with <li> tags for HTML display
                bullet_text = re.sub(bold_pattern, r"<b>\1</b>", line[2:].strip())
                formatted_lines.append(f"<li>{bullet_text}</li>")
            else:
                # Handle inline bold formatting in general text
                formatted_text = re.sub(bold_pattern, r"<b>\1</b>", line)
                formatted_lines.append(f"{formatted_text}")

        # Join the formatted lines into a single HTML response
        formatted_response = "".join(formatted_lines)

        return formatted_response
    except Exception as e:
        print(f"Error formatting Gemini response: {e}")
        return "<p>Sorry, there was an error processing the response.</p>"












#milestone 1    
def get_doctors_from_firebase():
    ref = db.reference('doctors')  # Adjust to your Firebase path
    doctors = ref.get()
    doctor_list = []
    
    # Extract the doctor's name and specialty from each doctor node
    if doctors:
        for doctor_id, doctor_data in doctors.items():
            name = doctor_data.get('name', 'Unknown')
            specialty = doctor_data.get('speciality', 'Unknown')
            bookurls = doctor_data.get('bookurls', 'Unknown')
            doctor_list.append({'name': name, 'speciality': specialty, 'bookurls': bookurls})
            print("BOOK URLS OF DOCTORS",bookurls)
    return doctor_list    

def greet(text):
    doc = nlp(text)
    trigger_phrases = ["hi", "hola", "hey"]
    for phrase in trigger_phrases:
        if phrase.lower() in text.lower():
            return True
    return False


def features(text):
    doc = nlp(text)
    trigger_phrases = ["what are your features", "what are your functionalities", "hey tell me what you can do", "what are you", "what are your features", "tell me about your features", "what can you help with me with", "what can you do", "tell me what you can do", "what is your purpose", "your core functionalties", "what are your core functionalities" ]
    for phrase in trigger_phrases:
        if phrase.lower() in text.lower():
            return True
    return False

    

def detect_doctor_list_intent(text):
    doc = nlp(text)
    trigger_phrases = ["show doctor list", "doctor list", "available doctors"]
    for phrase in trigger_phrases:
        if phrase.lower() in text.lower():
            return True
    return False

# Function to detect and translate to English
def english_translator(user_input: str) -> str:
    """
    Translates the input message to English if it's not already in English.
    """
    # Detect language first
    detected_lang = translator.detect(user_input).lang
    print(detected_lang)
    # If the detected language is not English, translate it
    if detected_lang != 'en':
        translated = translator.translate(user_input, src=detected_lang, dest='en')
        print(translated)
        return translated.text, detected_lang
    else:
        return user_input, detected_lang  # No translation needed if it's already in English
    
    
    
    
# Function to translate the chatbot's response back to the detected language
def translate_chatbot_response_back_to_detected_lang(response: str, detected_lang: str) -> str:
    """
    Translates the chatbot's response back to the user's detected language.
    
    Parameters:
    - response: The chatbot's response in English (or the original response).
    - detected_lang: The language code of the user's detected language (e.g., 'es' for Spanish, 'fr' for French).
    
    Returns:
    - The chatbot's response translated back to the detected language.
    """
    print("translation back happening",response)
    if detected_lang != 'en':
        # Translate the response into the detected language
        translated_response = translator.translate(response, dest=detected_lang).text
       
        print("RRRR",translated_response)
        return f"{translated_response}\n\n <b><u>In English</u></b>: {response}"
    else:
        # If the language is already English, return the response as is
        return response
    
def translate_doctor_list(doctors, detected_lang):
    print("in the doctor list format box")
    translated_doctors = []
    for doctor in doctors:
        translated_name = translate_chatbot_response_back_to_detected_lang(doctor['name'], detected_lang)
        translated_speciality = translate_chatbot_response_back_to_detected_lang(doctor['speciality'], detected_lang)
        bookurls = doctor['bookurls']
        translated_doctors.append({
            'name': translated_name,
            'speciality': translated_speciality,
            'bookurls': bookurls
        })
    return translated_doctors   


def handle_urgent_care(input_text):
    # Pass input to Gemini model for urgent care validation
    prompt = f"Is this an urgent care life or death situation like an accident or something else? Input: {input_text} REPLY YES OR NO ONLY"
    print("IN THE URGENT CARE BLOCK")
    # Assuming `gemini` is a function or API call to Gemini
    response = summarize_with_gemini_ifnofda(prompt)
    
    # Check Gemini's response for urgency
    if response == "Yes":
        # If Gemini confirms it's urgent, set the intent
       # urgentcareinput = True
       # urgent_dynamic_doctor(urgentcareinput,input_text)
        return True
    else:
        # If it's not urgent, return a generic response
        return False

def urgent_dynamic_doctor(urgentcareinput, input_text):
    if urgentcareinput:
        print("IN THE URGENT DYNAMIC DOCTOR BLOCK", urgentcareinput)
        
        # Fetch doctors from Firebase based on the urgent care input
        doctors_list = get_doctors_from_firebase()
        print(f"Doctors List from urgentcareinput: {doctors_list}")
        
        if not doctors_list:
            print("No doctors found in the system.")
            return "No doctors available for urgent care."

        # Create a formatted list of doctors and specialties
        doctor_string = ', '.join([f"{doctor['name']} + {doctor['speciality']}" for doctor in doctors_list])
        print("DOCTOR STRING CREATED")

        # Send the doctor list and the input to Gemini for the best specialty suggestion
        prompt = f"Given the urgent care situation: {input_text}, which doctor specialty is best for treatment? Here are the available doctors and specialties: {doctor_string}, CHOOSE ONE and return the response as DR NAME strictly no dot after DR, if no doctor is eligible then strictly reply Urgent Care Casualty" 
        prompt_1 = f"Given the urgent care situation: {input_text}, which doctor specialty is best for treatment? Here are the available doctors and specialties: {doctor_string}, CHOOSE ONE and return the response as DR NAME available with us right now for this urgent situation is is DR name, speciality is in the response and bold the doctor names and speciality, and provide 5 emergency steps to be taken for the urgent care secanrio,if no doctor is eligible then strictly reply Right now we dont have a doctor available to treat the specific symptom hence i ll be referring you to the <b>URGENT CARE CASUALTY</b>, and still give and provide 5 emergency steps to be taken for the urgent care secanrio ,also dont say about the other speciality doctor and about their speciality"
        try:
            doctor_response = summarize_with_gemini_ifnofda(prompt_1)
            print("normal doctor response:",doctor_response)
            doctor_response_docchoice = summarize_with_gemini_ifnofda(prompt)
            lowerdoc = format_gemini_response(doctor_response_docchoice.lower())
            print(f"Gemini Response for doctor choice is after formatting: {lowerdoc}")
            
# Return the response and the chosen doctor's name
            return {
                "response": doctor_response,
                "urgentcare_chosen_doc_name": lowerdoc
                }
        except Exception as e:
            print(f"Error during Gemini API call: {e}")
            return "An error occurred while processing your request."
    else:
        return "No urgent care required at the moment."


@app.route("/boot/chatbot", methods=["POST"])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def chatbot():
    """Handle user interactions with the chatbot."""
    try:
        data = request.get_json()
        nutritionflag = 0
        if not data or "message" not in data:
            return jsonify({"response": "Message is required."}), 400

        user_message = data["message"].strip().lower() 
        
        print(user_message)
        translated_message, detected_lang = english_translator(user_message)

        print("translation sucess for processing",translated_message,"detected lang is",detected_lang)
        # Case 1: Prompt for specifying medicines
        if "information on medicines" in translated_message.lower():
            print("CONTROLL HEREEE")
            response1 = "Sure, please provide the names of the medicines."
            final_response = translate_chatbot_response_back_to_detected_lang(response1, detected_lang)
            return jsonify({"response": final_response})
            

        # Case 2: Validate and process comma-separated medicine name        
        elif "information on" in translated_message and "," in translated_message:  # Ensure 'information on' and ',' are present
            print("info + , block")
        # Extract the part of the string after "information on"
            medicine_name_str = translated_message.lower().split("information on", 1)[1].strip()
            print("control here1")
        # Split the string by commas to separate multiple medicine names
            medicine_names = [name.strip() for name in medicine_name_str.split(",")]
            print("control here2")
            # Validate each medicine name and fetch data
            results = {}
            for medicine_name in medicine_names:
            # Debugging print statement to verify medicine names
                print(f"Validating medicine: {medicine_name}")

                if validate_medicine_names(medicine_name):  # Validate the name
                    medicine_data = fetch_medicine_data(medicine_name)
                    print(f"Validated medicine:{medicine_name}")
                    if medicine_data:
                        results[medicine_name] = summarize_medicine_info(medicine_data)
                    else:
                        prompt11 = f"Give a summary of under 120 words on {medicine_name} include all its use cases, precautions, and age group etc, bold all terms that are important."
                        results[medicine_name] = format_gemini_response(summarize_with_gemini_ifnofda(prompt11))
                else:
                    prompt22 = f"So say that this {medicine_name} is not a medicine, but if {medicine_name} is not at all related to medicine stirctly, then say I am sorry please specify medicines and health related words, otherwise give a summary on {medicine_name} of 40 words also stating what kind of substance it is and everything in general about it"                     
                    t1=formatted_response = format_gemini_response(summarize_with_gemini_ifnofda(prompt22))
                    results[medicine_name] = t1
                    
                
                    
        
        
        elif "information on"  in translated_message.lower():  # Ensure 'information on' and ',' are present
            print("in the info on block")
        # Extract the part of the string after "information on"

        # Split the string by commas to separate multiple medicine names
            medicine_name = translated_message.lower().split("information on", 1)[1].strip()

            # Validate each medicine name and fetch data
            results = {}
        
            # Debugging print statement to verify medicine names
            print(f"Validating medicine: {medicine_name}")

            if validate_medicine_names(medicine_name):  # Validate the name
                medicine_data = fetch_medicine_data(medicine_name)
                print(f"Validated medicine:{medicine_name}")
                if medicine_data:
                        results[medicine_name] = format_gemini_response(summarize_medicine_info(medicine_data))
                else:
                    prompt22 = f"Give a summary of under 120 words on {medicine_name} include all its use cases, precautions, and age group etc, bold every term that is important"
                    t1=formatted_response = format_gemini_response(summarize_with_gemini_ifnofda(prompt22))
                    results[medicine_name] = t1
        
            else:
                
                prompt22 = f"So say that this {medicine_name} is not a medicine, but if {medicine_name} is not at all related to medicine stirctly, then say I am sorry please specify medicines and health related words, otherwise give a summary on {medicine_name} of 40 words also stating what kind of substance it is and everything in general about it"     
                t1=formatted_response = format_gemini_response(summarize_with_gemini_ifnofda(prompt22))
                results[medicine_name] = t1
        
        elif "upload" in translated_message.lower() or "prescription" in translated_message.lower():
            response1 =  "Please upload your prescription file by using the upload prescription button in chat below or upload anytime button"
            final_response = translate_chatbot_response_back_to_detected_lang(response1, detected_lang)
            return jsonify({
                "response": final_response,
                "show_upload": True,  # This flag triggers the frontend to show the upload button
                })
            
            
           
            
            
        elif "logout" in translated_message.lower():
            logout()
            response1 =  "Okay Loggging you out"
            final_response = translate_chatbot_response_back_to_detected_lang(response1, detected_lang)
            return jsonify({
                "response": final_response,
                "show_logout": True,  # This flag triggers the frontend to show the upload button
                })
        
            
            
          # type: ignore # Custom NLP logic
        elif greet(translated_message.lower()):
            response1 = "Hello! How can I assist you today?"
            final_response = translate_chatbot_response_back_to_detected_lang(response1, detected_lang)
            return jsonify({"response": final_response})
       
       
       
       
        elif features(translated_message.lower()):
           # Return a response with features and dynamic buttons
            response = {
                "response": "Hello! I am <b>Cure Connect Chatbot</b>, an AI-powered assistant designed to help you with a variety of healthcare-related tasks. Whether you need assistance with appointments, symptom translation, or urgent care handling, I’ve got you covered. I can also provide medicinal information, pharmacy details, and help with dynamic message translation. Powered by advanced technology, I strive to provide fast, accurate, and helpful responses to all your health-related needs😊",
                "buttons": [
                    {"text": "APPOINTMENTS", "value": "appointments"},
                    {"text": "SYMPTOM TRANSLATION AND DIAGNOSIS", "value": "symptom_translation"},
                    {"text": "URGENT CARE HANDLING and SOS", "value": "urgent_care"},
                    {"text": "MEDICINAL INFORMATION", "value": "medicinal_info"},
                    {"text": "PHARMACY", "value": "pharmacy"},
                    {"text": "DYNAMIC MESSAGE TRANSLATION", "value": "dynamic_translation"}
                ],
                "emoji": "😊"
            }
            final_response = translate_chatbot_response_back_to_detected_lang(response, detected_lang)
            return final_response
            
       
        elif nutrition(translated_message.lower()):
            response1 = """Sure, I can provide a well-structured nutrition plan.  
            Please provide the following details:  
            - Height  
            - Weight  
            - Age  
            - Gender  
            - Body Goals Description  
            """
            nutritionflag = 1
            return jsonify({"response": response1, "nutritionflag": nutritionflag})

        
        elif "symptom translation and diagnosis" in translated_message.lower():
            response1 = "Click on the menu button and choose Symptom trasnlation, or you can directly type it in message and I ll do the translation and diagnosis for you 😊"
            final_response = translate_chatbot_response_back_to_detected_lang(response1, detected_lang)
            return jsonify({"response": final_response})
            
            
        elif "urgent care handling and sos" in translated_message.lower():
            response1 = "I can help in handling urgent care scenarios, type in your urgent care secanrio and I ll make sure you find the right doctor for helping you.(<b><u>DISCLAIMER</u></b>: I assign doctors only from Cure Connect Hospitals Group). I can handle SOS situations too, if you are in need of a emergency feel free to <b><u>click the SOS button</u></b> on top, or <b><u>type SOS</u></b>"
            final_response = translate_chatbot_response_back_to_detected_lang(response1, detected_lang)
            return jsonify({"response": final_response})    
        
        
        elif "dynamic message translation" in translated_message.lower():
            response1 = "You can type your queries in any language ranging from Hindi, Kannada, French, Russian etc.I ll reply back to you in the same language, I am designed to handle all your requests as your friend, feel free to text you in your comfortable language 😊"
            final_response = translate_chatbot_response_back_to_detected_lang(response1, detected_lang)
            return jsonify({"response": final_response})  
        
        elif "pharmacy" in translated_message.lower():
            response1 = "Explore a wide range of products form our online pharmacy click the menu and select Pharmacy 😊"
            final_response = translate_chatbot_response_back_to_detected_lang(response1, detected_lang)
            return jsonify({"response": final_response}) 
        
        elif "medicinal information" in translated_message.lower():
            response1 = "I can give you information on medicinal terms, medicines, diseases and many more. I have a large knowledge on a lot of medicines, feel free to type in your queries 😊"
            final_response = translate_chatbot_response_back_to_detected_lang(response1, detected_lang)
            return jsonify({"response": final_response})   
            
        elif 'list of doctors' in translated_message.lower():
            print("in list of doctors block")
            doctors = get_doctors_from_firebase()
            print(doctors)
            translated_doctors = translate_doctor_list(doctors, detected_lang)
            print("doctors list",translated_doctors)
            return jsonify({"doctors": translated_doctors})     
        
        elif 'book' and 'appointment' in translated_message.lower():
            print("in book appointment block")
            doctors = get_doctors_from_firebase()
            print("ssss",doctors)
            translated_doctors = translate_doctor_list(doctors, detected_lang)
            print("doctors list",translated_doctors)
          
            return jsonify({"doctors": translated_doctors})
        
            
        elif 'reschedule' in translated_message.lower():
            response1 = "Check your email for the reschedule link."
            final_response = translate_chatbot_response_back_to_detected_lang(response1, detected_lang)
            return jsonify({"response": final_response})

        
               
        elif 'thank you' in translated_message.lower() or 'done' in translated_message.lower():
            response1 = "You're welcome! Feel free to reach out for further assistance."
            final_response = translate_chatbot_response_back_to_detected_lang(response1, detected_lang)
            return jsonify({"response": final_response})
        
        elif detect_doctor_list_intent(translated_message.lower()):
            print("IN THE DETECT DOCTOR LIST BLOCK")
            doctors = get_doctors_from_firebase()
            print("list function working",doctors)
            translated_doctors = translate_doctor_list(doctors, detected_lang)
            print("doctors list",translated_doctors)
          
            return jsonify({"doctors": translated_doctors})        
        
         # Check if the user input indicates an urgent care situation
        
        elif detect_disease_or_symptom(translated_message.lower()):
            print("IN THE SYMPTOM BLOCK",translated_message)
            prompt_health = (
                f"IF The input contains disease or symptom-related information for example high fever etc. Provide healthy tips,suggest some general medicines,make sure atleast 5 healthy tips in points are given and then end with a consult doctor prompt also bold the consult doctor heading, medicines, other important information terms strictly,\nInput: {translated_message.lower()}, "
                f"If the input involves medicine names just reply accordingly to what is asked whether its a comparison or general info. Keep the response between 80 to 60 words"
                f"If the input is just a general information related to  info on medical procedures like cpr etc or general comparison between medical terms or health related information reply accordingly in a 60 to 80 word limit"
                f"If the input contains any life or death type situations like accidents like a heart attack, stroke etc respond TRUE only and not anything else, if the input is a what or which or why type or comparison type question related to medicine answer accordingly in 60 to 80 words but dont say things like Since the input is a what type question related to medicine, no healthy tips or general medicines are needed here. This response is within the 60-80 word limit."
            )
            print("IN THE SYMPTOM HANDLING PART")
            summary_response = summarize_with_gemini_ifnofda(prompt_health)
            if summary_response == "TRUE":
                urgentcareinput = True
                print("IN THE URGENT CARE BLOCK1")
                urgent_care_result = urgent_dynamic_doctor(urgentcareinput, translated_message.lower())
                urgent_care_response = urgent_care_result.get("response")
                ugcaredocname = urgent_care_result.get("urgentcare_chosen_doc_name")
                print("IN THE URGENT CARE BLOCK222", ugcaredocname)
                ugcare = "TRUE"
                newresponse = urgent_care_response
                print("response from dynamic doctor", newresponse)
            else:
                newresponse = summary_response
                ugcare = "FALSE"   
                ugcaredocname = "FALSE" 
            formatted_response = format_gemini_response(newresponse)
            prompt_intent = (
                f"for the input {translated_message.lower()} return the cause of emergency response strictly, dont return the doctor details or anything only the reason for example if its a heart attack respond as heart attack"
            )
            caseintent = format_gemini_response(summarize_with_gemini_ifnofda(prompt_intent))
            final_response = translate_chatbot_response_back_to_detected_lang(formatted_response, detected_lang)
            print("qqqq",final_response)
            print(ugcare)
            print(ugcaredocname)
            return jsonify({"response": final_response, "ugcare": ugcare, "urgentcare_chosen_doc_name": ugcaredocname, "caseINTENT": caseintent })

        
        
        elif ultimate_thankyou(translated_message.lower()):
            print("IN THE ultimate thankyou block",translated_message)
            prompt_health = (
                f"Is the word or text {user_message} is like a acknowledgemnet or a farewell text like bye, c ya, or thanks a lot, or anything similar then striclty respond with a warm message like i am glad i could help, if you have any queries feel free to ask, have a great day and also use one emoji like a smiling face dont include sentences like It's a farewell, similar to bye or cya."             
                )
            print("IN THe ultimate thankyou part after response generated")
            summary_response = summarize_with_gemini_ifnofda(prompt_health)
            
            newresponse = summary_response
            print("response from thankyouuu geminii", newresponse)
            formatted_response = format_gemini_response(newresponse)
            final_response = translate_chatbot_response_back_to_detected_lang(formatted_response, detected_lang)
            print("qqqq",final_response)
            return jsonify({"response": final_response})
        
        
        else:
            unrelated_prompt = (
                    "This input does not seem related to health, medicine, or diseases.Please provide a message relevant to these topics."
                )
            final_response = translate_chatbot_response_back_to_detected_lang(unrelated_prompt, detected_lang)

            return jsonify({"response": final_response})

    
            

        
                       
       
        
        
        if results:
           # Format the results with double line breaks for separation
            formatted_results = "<p>" + "</p><p>".join([f"<b>{key}</b>: {value}" for key, value in results.items()]) + "</p>"
            final_response = format_gemini_response(translate_chatbot_response_back_to_detected_lang(formatted_results, detected_lang))
            print("FORMATTED RESULTS=",formatted_results)
            
            print("Final Response=",final_response)
            return jsonify({"response": final_response})
        else:
            return jsonify({"response": "I couldn't process your request. Please try again with valid inputs."})

       
        
    except Exception as e:
        return jsonify({"response": "Sorry I cant process what you typed, I can help in getting information about medicines and prescriptions as well as help in booking and rescheduling appointments "}), 500






# Function to send email
def send_email(patient_name, doctor_name, doctor_email, case_intent, room_link):
    sender_email = ""  # Your email address, MAKE IT DYNAMIC IN THE FUTURE
    sender_password = ""  # Your email password
    print("hereee nowwww")
    # SMTP server configuration
    smtp_server = "smtp.gmail.com"
    smtp_port = 587  # Use 465 for SSL or 587 for TLS

    try:
        # Prepare the email subject and body
        subject = f"URGENT CARE: {case_intent} - Immediate Assistance Needed"
        body = (f"Dear {doctor_name},\n\n"
                f"We have an urgent care case from {patient_name}.\n\n"
                f"Case Intent: {case_intent}\n\n"
                f"Please click the link below to start the video call and assist the patient:\n"
                f"{room_link}\n\n"
                "Best regards,\nYour Healthcare Team")

        # Create message object
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = doctor_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Connect to the SMTP server and send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Secure the connection
            server.login(sender_email, sender_password)  # Login to the email account
            server.sendmail(sender_email, doctor_email, msg.as_string())  # Send the email
            print(f"Email sent to {doctor_email}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


CLIENT_ID = "RBl7LXhPSHy8mFYhRBsmtg"
CLIENT_SECRET = "6ziWyfLWClrMXCa6G9M590TIdS4DDdk7"
ACCOUNT_ID = "CInN3oxUQhmTZfwjtqtwLQ"

def get_zoom_access_token():
    """Fetches the OAuth access token from Zoom"""
    print("hereee")
    url = "https://zoom.us/oauth/token"
    auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
    auth_bytes = auth_string.encode("utf-8")
    auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

    headers = {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "account_credentials",
        "account_id": ACCOUNT_ID
    }
    print("log hereee")
    response = requests.post(url, headers=headers, data=data)
    print("token is:", response)
    if response.status_code == 200:
        print("token generation successful")
        return response.json().get("access_token")
    else:
        print("token generation fail")
        return None



def get_token():
    """API Endpoint to get Zoom access token"""
    token = get_zoom_access_token()
    if token:
        return jsonify({"access_token": token}), 200
    else:
        return jsonify({"error": "Failed to get access token"}), 400

def create_zoom_meeting():
    """API Endpoint to create a Zoom meeting"""
    access_token = get_zoom_access_token()
    if not access_token:
        return jsonify({"error": "Failed to get access token"}), 400
    print("acess token is in create zoom meet:", access_token)
    url = "https://api.zoom.us/v2/users/me/meetings"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    meeting_details = {
        "topic": "Urgent Care Consultation",
        "type": 2,  # Scheduled meeting
        "start_time": "2025-02-01T15:00:00Z",  # Set dynamically
        "duration": 30,  # In minutes
        "timezone": "UTC",
        "agenda": "Urgent care consultation with a doctor"
    }

    response = requests.post(url, headers=headers, json=meeting_details)

    if response.status_code == 201:
        meeting_info = response.json()
        return meeting_info["join_url"], meeting_info["start_url"]  # Return both URLs
    else:
        return jsonify({"error": response.text}), response.status_code

# Function to handle the urgent care email request
@app.route('/boot/urgentsendemail', methods=['POST'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def urgent_send_email():
    try:
        # Get the request data
        data = request.json
        doctor_name = data.get('doctor_name').upper()  # Convert doctor name to upper case
        case_intent = data.get('case_intent')

        # Simulating JWT verification
        user_id = "-OHnvOsCJu7a9hN84-Mt"
        email = "rohanbaiju210@gmail.com"
        print("USER ID FROM update cart VERIFY TOKEN IS", user_id, "EMAIL IS", email)

        if not user_id:
            print("JWT TOKEN ERROR")
            return jsonify({"error": "JWT token is invalid or expired. Please log in again."}), 403
        print("JWT VERIFIED user id from update cart is", user_id)

        # Initialize Realtime Database client
        ref = db.reference()

        # Fetch user details from Realtime Database
        user_ref = ref.child('users').child(user_id)
        user = user_ref.get()

        if not user:
            return jsonify({"response": "User not found."}), 400

        user_name = user.get('name')

        # Fetch doctors from Realtime Database
        doctors_ref = ref.child('doctors')
        doctors = doctors_ref.get()

        doctor_email = None
        for doctor_id, doctor_data in doctors.items():
            stored_doctor_name = doctor_data.get('name').upper()
            if stored_doctor_name == doctor_name:
                doctor_email = doctor_data.get('docemail')
                break

        if not doctor_email and doctor_name == "URGENT CARE CASUALTY":
            doctor_name = "URGENT CARE CASUALTY"
            doctor_email = ""
        
        # Generate the Zoom meeting link
        print("before zoom")
        join_url, start_url = create_zoom_meeting()  # Get the Zoom meeting URLs

        if isinstance(join_url, str) and isinstance(start_url, str):  # Check if both URLs are strings
            print("after zoom join url is:", join_url)
            print("start url:", start_url)

            # Send the email with the Zoom room link
            email_sent = send_email(user_name, doctor_name, doctor_email, case_intent, start_url)
            if email_sent:
                return jsonify({"response": join_url}), 200
            else:
                return jsonify({"error": "Failed to send email. Please try again later."}), 500
        else:
            # Handle errors returned from create_zoom_meeting()
            return join_url  # This contains the error message returned by the Zoom API

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "An error occurred while processing your request."}), 500

@app.route('/boot/translaterr', methods=['POST'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def translate():
    data = request.json
    text = data.get('text')

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        translated = translator.translate(text, dest='en')  # English is the default target language
        return jsonify({"translated_text": translated.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



def symptomtrans_senddetails(user_id):
    
        # Initialize Realtime Database client
    ref = db.reference()

        # Fetch user details from Realtime Database
    user_ref = ref.child('users').child(user_id)
    user = user_ref.get()
    print("is hereeeeeeee synptom trans")
    if not user:
        print("sscscscscscscsc")
        return jsonify({"response": "User not found."}), 400

    user_name1 = user.get('name')
    print(user_name1)
    symptomhandling = "SYMPTOM HANDLING"
    print(symptomhandling)
    return({"user_name": user_name1})
    
    
    
    

def send_email22(patient_name,user_email,case_intent):
    
    print("email 2222 blockkk enteredddd")
    sender_email = user_email
    print(sender_email)# Your email address, MAKE IT DYNAMIC IN THE FUTURE
    sender_password = ""  # Your email password
    doctor_email = ""
    doctor_name ="Casualty"   # SMTP server configuration
    smtp_server = "smtp.gmail.com"
    smtp_port = 587  # Use 465 for SSL or 587 for TLS
    print("smtp done for email22222")
    try:
        # Prepare the email
        subject = f"SYMPTOMS : {case_intent}"
        body = f"Dear {doctor_name},\n\nI need urgent assistance regarding my symptoms. Symptoms are: {case_intent}; I need your help. Please help me. My name is {patient_name}.\n\nBest regards."

        # Create message object
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = doctor_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        print("msssggg parseddddd")
        # Connect to the SMTP server and send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Secure the connection
            server.login(sender_email, sender_password)  # Login to the email account
            server.sendmail(sender_email, doctor_email, msg.as_string())  # Send the email
            print(f"Email sent to {doctor_email}")
            print("chjeckkkkk meeeeee")
        return True
    except Exception as e:
        print(f"Error sending email, email should be valid gmail id: {e}")
        return False    
    
    
    
@app.route('/boot/submit-symptoms', methods=['POST'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def submit_symptoms():
    data = request.json
    symptoms = data.get('symptoms')
    print(symptoms)
    user_id,user_email = verify_token()  # For testing purposes, use your real logic here
        # email = "uuu.com"  # Also mock for testing
    print("USER ID FROM update cart VERIFY TOKEN IS", user_id, "EMAIL IS", user_email)
    print(user_email)
    if not user_id:
            print("JWT TOKEN ERROR")
            return jsonify({"error": "JWT token is invalid or expired. Please log in again."}), 403
    print("JWT VERIFIED user id from update cart is", user_id)

    print("xxxxxxx")
    if not symptoms:
        return jsonify({"error": "No symptoms provided"}), 400
    print("sssssss")
    try:
        #user_name2 = symptomtrans_senddetails(user_id)
        ref = db.reference()

        # Fetch user details from Realtime Database
        user_ref = ref.child('users').child(user_id)
        user = user_ref.get()
        print("is hereeeeeeee synptom trans")
        if not user:
            print("sscscscscscscsc")
            return jsonify({"response": "User not found."}), 400

        user_name2 = user.get('name')
        print(user_name2)
        print("ggggggg")
        print(user_name2)
        email_sent = send_email22(user_name2,user_email,symptoms)
        print("qqqqqqqqq")
        if email_sent:
            print("ttttttttttt")
            return jsonify({"response": f"Email sent successfully to rohanbaiju210@gmail.com from {user_email}.", "success": "TRUE"}), 200
        else:
            print("ffffffffffff")
            return jsonify({"response": "Failed to send email. Please try again later, also user should have valid gmail id", "success": "FALSE"}), 500
            
        # return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



def summarize_with_gemini_ifnofda(prompt1):
    """Generate a summary using Google Gemini."""
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt1)
    return response.text.strip()



@app.route('/boot/search', methods=['POST'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def search_medicines():
    try:
        # Get the user input from the request
        data = request.json
        search_query = data.get('query', '')
        #user_id,email = verify_token()  # For testing purposes, use your real logic here
        # email = "uuu.com"  # Also mock for testing
        #print("USER ID FROM update cart VERIFY TOKEN IS", user_id, "EMAIL IS", email)

        #if not user_id:
            #print("JWT TOKEN ERROR")
            #return jsonify({"error": "JWT token is invalid or expired. Please log in again."}), 403
        #print("JWT VERIFIED user id from update cart is", user_id)

        if not search_query:
            return jsonify({'error': 'Query is required'}), 400

        # Query OpenFDA API
        params = {
            'search': f"openfda.brand_name:{search_query}*",
            'limit': 3
        }

        response = requests.get(OPENFDA_BASE_URL, params=params)
        response.raise_for_status()  # Raise an error for HTTP issues

        # Parse response data
        results = response.json().get('results', [])
        medicines = []

        for result in results:
            product_name = result.get('openfda', {}).get('generic_name', ['Unknown'])[0]
            brand_name = result.get('openfda', {}).get('brand_name', ['Unknown'])[0]
            manufacturer_name = result.get('openfda', {}).get('manufacturer_name', ['Unknown'])[0]

            # Fetch description from Gemini
            #gemini_description = generate_gemini_description(product_name)

            medicines.append({
                'product_name': product_name,
                'brand_name': brand_name,
                'manufacturer_name': manufacturer_name,
               # 'description': gemini_description commented so that resource exhaustion is eliminated
            })

        return jsonify({'medicines': medicines}), 200

    except requests.exceptions.RequestException as e:
        return jsonify({'error': f"Medicine not found in openfda"}), 500
    except KeyError:
        return jsonify({'medicines': []}), 200  # Handle no results






def get_image_from_google_search(query):
    """Fetch image from Google Custom Search API"""
    url = f"https://www.googleapis.com/customsearch/v1?q={query}&cx={GOOGLE_CSE_ID}&searchType=image&key={GOOGLE_API_KEY}"
    print("ree",query)
    response = requests.get(url)
    data = response.json()
    
    if 'items' in data:
        image_url = data['items'][0]['link'] # Get the first image link
        print(image_url)
        return image_url
    return "NO IMAGE URL OR API EXHAUSTED CHECK GOOGLE CLOUD CONSOLE FOR ANALYTICS"



@app.route('/boot/dynamicpage', methods=['POST'])
@cross_origin(origin='*', headers=['Content-Type', 'Authorization'])
def dynamic_page_data():
    """Main function to get image, OpenFDA data, and Gemini description"""
    # Parse the incoming JSON data
    data = request.get_json()
    brand_name = data.get('brand_name', '')
    print(brand_name, "dwsdsdsdsdswd")
    if not brand_name:
        return jsonify({"message": "Brand name is required"}), 400

    # Get image from Google or Amazon (previous function)
    image_url = get_image_from_google_search(brand_name)
    print(image_url)
    if not image_url:
        print("no image")
        return jsonify({"message": "No image found"}), 404

    print("chk hereeeee")
    # Initialize variables for manufacturer, warnings, and storage
    manufacturer, warnings, storage = None, None, None

    # Fetch OpenFDA data (manufacturer, warnings, storage)
    manufacturer, warnings, storage = get_openfda_data(brand_name)
    print(warnings)
    print(storage)
    if manufacturer is None:
        print("fgfgfgffgfgf")
        prompt1 = f"Give a 4 line information on the warnings and precautions of the medicinal product {brand_name}  bold important terms"
        warnings = format_gemini_response2222(summarize_with_gemini_ifnofda(prompt1))
        manufacturer = "CURE CONNECT LIMITED"
        prompt2 = f"Give a 4 line information on the storage requirements of the medicinal product {brand_name}  bold important terms"
        storage = format_gemini_response2222(summarize_with_gemini_ifnofda(prompt2))
    else:
        print("sdsdsdsdsdd")
        # Fetch OpenFDA data (manufacturer, warnings, storage)
        manufacturer, warnings, storage = get_openfda_data(brand_name)

    prompt = f"Give a 3 line description on the medicinal product {brand_name}, mention its use cases and effects, bold important terms"
    # Fetch description from Gemini
    description = format_gemini_response2222(summarize_with_gemini_ifnofda(prompt))
    print(description)
    
    # Return the combined data
    return jsonify({
        "image_url": image_url,
        "brand_name": brand_name,
        "manufacturer": manufacturer,
        "warnings": warnings,
        "storage": storage,
        "description": description
    })





def summarize_with_gemini_ifnofda(prompt1):
    """Generate a summary using Google Gemini."""
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt1)
    return response.text.strip()


"""Fetch medicine details from OpenFDA"""

def get_openfda_data(brand_name):
    """Fetch manufacturer, warnings, and storage details from OpenFDA"""
    try:
        params = {"search": f"openfda.brand_name:{brand_name}", "limit": 1}
        response = requests.get(OPENFDA_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        print("Reached in OpenFDA")

        if data.get("results"):
            result = data["results"][0]

            manufacturer = result.get("openfda", {}).get("manufacturer_name", ["N/A"])[0]
            warnings = result.get("warnings", ["N/A"])[0]
            prompt22 = f"Convert this {warnings} into a shorter paragraph of say 60 words, if no content then use {brand_name} and summarise its warnings in less than 60 words and strictly bold all important terms, if no warnings are there at all then strictly respond by saying No Warnings available, dont include sentences like  No content provided to shorten. Therefore, here's a summary"
            warnings1 = format_gemini_response2222(summarize_with_gemini_ifnofda(prompt22))
            storage = result.get("storage_and_handling", ["N/A"])[0]
            prompt23 = f"Summarise this {storage} into a shorter paragraph of say 60 words, if no content then use {brand_name} and summarise its storage requirements in less than 60 words and strictly bold all important storage requirememts like temprature etc, if no storage requirements is there striclty respond No Storage Requirements, dont say sentences like Please provide the N/A content you wish me to summarize. I need the text to be able to create a summary."
            storage1 = format_gemini_response2222(summarize_with_gemini_ifnofda(prompt23))
            return manufacturer, warnings1, storage1  # Returning the values in the correct order

        return None, None, None  # If no data found, return None values

    except requests.RequestException as e:
        print("Error fetching OpenFDA data:", e)
        return None, None, None


if __name__ == '__main__':
    app.run(debug=True)






 










""""
elif "," in translated_message.lower():  # Ensure 'information on' and ',' are present
            print("in the , block")
        # Extract the part of the string after "information on"

        # Split the string by commas to separate multiple medicine names
            medicine_names = [name.strip() for name in translated_message.split(",")]

            # Validate each medicine name and fetch data
            results = {}
            for medicine_name in medicine_names:
            # Debugging print statement to verify medicine names
                print(f"Validating medicine: {medicine_name}")

                if validate_medicine_names(medicine_name):  # Validate the name
                    medicine_data = fetch_medicine_data(medicine_name)
                    print(f"Validated medicine:{medicine_name}")
                    if medicine_data:
                        results[medicine_name] = format_gemini_response(summarize_medicine_info(medicine_data))
                    else:
                        prompt11 = f"Give a summary of under 120 words on {medicine_name} include all its use cases, precautions, and age group etc, strictly make sure you bold all terms that are important"
                        results[medicine_name] = format_gemini_response(summarize_with_gemini_ifnofda(prompt11))
        
                else:
                    
                    prompt22 = f"So say that this {medicine_name} is not a medicine, but if {medicine_name} is not at all related to medicine stirctly, then say I am sorry please specify medicines and health related words, otherwise give a summary on {medicine_name} of 40 words also stating what kind of substance it is and everything in general about it, but if it is a symptom or disease related anything give proper and detailed summary to handle them and provide a consult a doctor message in the end"     
                    t1=formatted_response = format_gemini_response(summarize_with_gemini_ifnofda(prompt22))
                    results[medicine_name] = t1
        
        
        
        
# Function to interact with Gemini
def generate_gemini_description(product_name):
    try:
        gemini_prompt = f"Provide three concise three-word points describing the medical product '{product_name}'."

        # Initialize the Gemini model
        model = genai.GenerativeModel("gemini-1.5-flash")
        gemini_response = model.generate_content(gemini_prompt)
        
        # Debug print to inspect the response
        print(f"Gemini response: {gemini_response}")

        descriptions = []
        # Parse the Gemini response
        for candidate in gemini_response.candidates:
            description_text = candidate.content.parts[0].text.strip()
            descriptions.append(description_text)

        return descriptions

    except Exception as e:
        print(f"Error during Gemini description generation: {e}")
        return ["Description not available"]  # Fallback description









        
            """