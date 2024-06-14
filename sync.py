import json
import time
import sqlite3
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Read values ​​from configuration file
print("Loading config...")
with open('config.json') as config_file:
    config = json.load(config_file)

ACCESS_TOKEN = config["ACCESS_TOKEN"]
WHATSAPP_BUSINESS_ACCOUNT_ID = config["WHATSAPP_BUSINESS_ACCOUNT_ID"]
DATABASE_PATH = config["DATABASE_PATH"]

print(f"ACCESS_TOKEN: {ACCESS_TOKEN}")
print(f"WHATSAPP_BUSINESS_ACCOUNT_ID: {WHATSAPP_BUSINESS_ACCOUNT_ID}")
print(f"DATABASE_PATH: {DATABASE_PATH}")

def read_inventory(database_path):
    print("Reading inventory from database...")
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        cursor.execute("SELECT Name, Price, Image FROM Product")
        products = cursor.fetchall()
        conn.close()
        print(f"Found {len(products)} products in the database.")
        return products
    except Exception as e:
        print(f"Error reading inventory: {e}")
        return []

def get_whatsapp_catalog():
    print("Fetching WhatsApp catalog...")
    try:
        url = f"https://graph.facebook.com/v17.0/{WHATSAPP_BUSINESS_ACCOUNT_ID}/products"
        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            catalog = response.json()['data']
            print(f"Found {len(catalog)} products in WhatsApp catalog.")
            return catalog
        else:
            print(f"Error fetching WhatsApp catalog: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Error fetching WhatsApp catalog: {e}")
        return []

def get_product_names_from_catalog(catalog):
    return {item['name']: item for item in catalog}

def upload_image_to_whatsapp(image_data):
    print("Uploading image to WhatsApp...")
    try:
        url = f"https://graph.facebook.com/v17.0/{WHATSAPP_BUSINESS_ACCOUNT_ID}/media"
        files = {
            'file': ('image.jpg', image_data, 'image/jpeg')
        }
        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}"
        }
        response = requests.post(url, files=files, headers=headers)
        if response.status_code == 200:
            media_id = response.json()['id']
            print(f"Image uploaded successfully. Media ID: {media_id}")
            return media_id
        else:
            print(f"Error uploading image: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error uploading image: {e}")
        return None

def add_or_update_product_in_whatsapp_catalog(product_name, price, image_data):
    print(f"Adding/updating product in WhatsApp catalog: {product_name}")
    try:
        media_id = upload_image_to_whatsapp(image_data)
        if not media_id:
            return None, "Failed to upload image"
        
        url = f"https://graph.facebook.com/v17.0/{WHATSAPP_BUSINESS_ACCOUNT_ID}/products"
        payload = {
            "name": product_name,
            "price_amount_1000": int(price * 1000),  # Because WhatsApp uses millimeter units for price.
            "currency": "EGP",
            "image_id": media_id,
            "is_hidden": False if price > 0 else True
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ACCESS_TOKEN}"
        }
        response = requests.post(url, json=payload, headers=headers)
        print(f"Response: {response.status_code} - {response.text}")
        return response.status_code, response.text
    except Exception as e:
        print(f"Error adding/updating product in WhatsApp catalog: {e}")
        return None, str(e)

def add_or_update_product_in_database(database_path, product_name, price, image_data):
    print(f"Adding/updating product in database: {product_name}")
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        cursor.execute("SELECT Name FROM Product WHERE Name = ?", (product_name,))
        result = cursor.fetchone()
        if result:
            cursor.execute("UPDATE Product SET Price = ?, Image = ? WHERE Name = ?", (price, image_data, product_name))
        else:
            cursor.execute("INSERT INTO Product (Name, Price, Image) VALUES (?, ?, ?)", (product_name, price, image_data))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error adding/updating product in database: {e}")

def sync_inventory_with_whatsapp(database_path):
    print("Syncing inventory with WhatsApp catalog...")
    try:
        products = read_inventory(database_path)
        print(f"Products from DB: {products}")
        whatsapp_catalog = get_whatsapp_catalog()
        print(f"WhatsApp Catalog: {whatsapp_catalog}")
        whatsapp_product_names = get_product_names_from_catalog(whatsapp_catalog)

        db_product_names = {product[0]: (product[1], product[2]) for product in products}

        # Synchronize quantities and prices and add missing products in the WhatsApp catalog
        for product_name, (price, image_data) in db_product_names.items():
            if product_name not in whatsapp_product_names:
                status, response = add_or_update_product_in_whatsapp_catalog(product_name, price, image_data)
                print(f"Added {product_name} to WhatsApp catalog: {status} - {response}")
            else:
                existing_product = whatsapp_product_names[product_name]
                if existing_product['price_amount_1000'] != int(price * 1000):
                    status, response = add_or_update_product_in_whatsapp_catalog(product_name, price, image_data)
                    print(f"Updated {product_name} in WhatsApp catalog: {status} - {response}")

        # Synchronize quantities and add missing products to the database
        for product_name, product_info in whatsapp_product_names.items():
            if product_name not in db_product_names:
                add_or_update_product_in_database(database_path, product_name, product_info['price_amount_1000'] / 1000, product_info['image_url'])
                print(f"Added {product_name} to the database.")
            else:
                if db_product_names[product_name][0] != product_info['price_amount_1000'] / 1000:
                    add_or_update_product_in_database(database_path, product_name, product_info['price_amount_1000'] / 1000, product_info['image_url'])
                    print(f"Updated {product_name} in the database.")
    except Exception as e:
        print(f"Error during sync: {e}")

# Manually call the sync function at the beginning to make sure it works.
sync_inventory_with_whatsapp(DATABASE_PATH)

class DatabaseEventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path == DATABASE_PATH:
            print(f"{DATABASE_PATH} has been modified, syncing...")
            sync_inventory_with_whatsapp(DATABASE_PATH)

# Setting up a change monitor
print("Setting up file system observer...")
event_handler = DatabaseEventHandler()
observer = Observer()
observer.schedule(event_handler, path=DATABASE_PATH, recursive=False)
observer.start()

print("Script is running. Monitoring for changes...")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()
