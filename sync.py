import json
import time
import sqlite3
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

print("Loading config...")
# Read values ​​from configuration file
with open('config.json') as config_file:
    config = json.load(config_file)

ACCESS_TOKEN = config["ACCESS_TOKEN"]
WHATSAPP_BUSINESS_ACCOUNT_ID = config["WHATSAPP_BUSINESS_ACCOUNT_ID"]
DATABASE_PATH = config["DATABASE_PATH"]

def read_inventory(database_path):
    print(f"Reading inventory from {database_path}")
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    cursor.execute("SELECT Name, stock_quantity, Price, ImageURL FROM Product")
    products = cursor.fetchall()
    conn.close()
    print(f"Found {len(products)} products in inventory")
    return products

def get_whatsapp_catalog():
    print("Fetching WhatsApp catalog...")
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_BUSINESS_ACCOUNT_ID}/products?fields=id,name,price_amount_1000,stock,media.images"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print("WhatsApp catalog fetched successfully")
        return response.json()['data']
    else:
        print(f"Error fetching WhatsApp catalog: {response.status_code} - {response.text}")
        return []

def get_product_names_from_catalog(catalog):
    return {item['name']: item for item in catalog}

def upload_image_to_whatsapp(image_url):
    print(f"Uploading image from {image_url} to WhatsApp...")
    url = f"https://graph.facebook.com/v20.0/{WHATSAPP_BUSINESS_ACCOUNT_ID}/media"
    payload = {
        "file": image_url,
        "type": "image",
        "messaging_product": "whatsapp"
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    response = requests.post(url, data=payload, headers=headers)
    if response.status_code == 200:
        print("Image uploaded successfully")
        return response.json()['id']
    else:
        print(f"Error uploading image to WhatsApp: {response.status_code} - {response.text}")
        return None

def add_or_update_product_in_whatsapp_catalog(product_id, product_name, stock_quantity, price, image_url):
    media_id = upload_image_to_whatsapp(image_url)
    if not media_id:
        print(f"Failed to upload image for {product_name}")
        return

    if product_id:
        print(f"Updating product {product_name} in WhatsApp catalog...")
        url = f"https://graph.facebook.com/v20.0/{product_id}"
        payload = {
            "name": product_name,
            "stock": stock_quantity,
            "currency": "EGP",
            "price_amount_1000": price * 1000,
            "media": [{"id": media_id}]
        }
        if stock_quantity > 0:
            payload["status"] = "active"
        else:
            payload["status"] = "hidden"
        response = requests.post(url, json=payload, headers=headers)
    else:
        print(f"Adding product {product_name} to WhatsApp catalog...")
        url = f"https://graph.facebook.com/v20.0/{WHATSAPP_BUSINESS_ACCOUNT_ID}/products"
        payload = {
            "name": product_name,
            "stock": stock_quantity,
            "currency": "EGP",
            "price_amount_1000": price * 1000,
            "media": [{"id": media_id}],
            "status": "active" if stock_quantity > 0 else "hidden"
        }
        response = requests.post(url, json=payload, headers=headers)

    return response.status_code, response.text

def add_or_update_product_in_database(database_path, product_name, stock_quantity, price, image_url):
    print(f"Updating/adding product {product_name} in database...")
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    cursor.execute("SELECT Name FROM Product WHERE Name = ?", (product_name,))
    result = cursor.fetchone()
    if result:
        cursor.execute("UPDATE Product SET stock_quantity = ?, Price = ?, ImageURL = ? WHERE Name = ?", (stock_quantity, price, image_url, product_name))
    else:
        cursor.execute("INSERT INTO Product (Name, stock_quantity, Price, ImageURL) VALUES (?, ?, ?, ?)", (product_name, stock_quantity, price, image_url))
    conn.commit()
    conn.close()
    print(f"Product {product_name} updated/added in database")

def sync_inventory_with_whatsapp(database_path):
    print("Starting inventory sync with WhatsApp...")
    products = read_inventory(database_path)
    whatsapp_catalog = get_whatsapp_catalog()
    whatsapp_product_names = get_product_names_from_catalog(whatsapp_catalog)

    db_product_names = {product[0]: (product[1], product[2], product[3]) for product in products}

    # Synchronize quantities and prices and add missing products in the WhatsApp catalog
    for product_name, (stock_quantity, price, image_url) in db_product_names.items():
        if product_name not in whatsapp_product_names:
            status, response = add_or_update_product_in_whatsapp_catalog(None, product_name, stock_quantity, price, image_url)
            print(f"Added {product_name} to WhatsApp catalog: {status} - {response}")
        else:
            existing_product = whatsapp_product_names[product_name]
            if existing_product['stock'] != stock_quantity or existing_product['price_amount_1000'] != price * 1000:
                status, response = add_or_update_product_in_whatsapp_catalog(existing_product['id'], product_name, stock_quantity, price, image_url)
                print(f"Updated {product_name} in WhatsApp catalog: {status} - {response}")

    # Synchronize quantities and add missing products to the database
    for product_name, product_info in whatsapp_product_names.items():
        if product_name not in db_product_names:
            add_or_update_product_in_database(database_path, product_name, product_info['stock'], product_info['price_amount_1000'] / 1000, product_info['media'][0]['id'] if 'media' in product_info and product_info['media'] else None)
            print(f"Added {product_name} to the database.")
        else:
            if db_product_names[product_name][0] != product_info['stock'] or db_product_names[product_name][1] != product_info['price_amount_1000'] / 1000:
                add_or_update_product_in_database(database_path, product_name, product_info['stock'], product_info['price_amount_1000'] / 1000, product_info['media'][0]['id'] if 'media' in product_info and product_info['media'] else None)
                print(f"Updated {product_name} in the database.")

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
    print("Stopping observer...")
    observer.stop()
observer.join()






