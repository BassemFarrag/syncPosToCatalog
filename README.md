# syncPosToCatalog
**Beta** A project for sync any pos system using sqlite to sync products with WhatsApp Catalog.
note: we used [Aronium - Lite](https://www.aronium.com/en/download) as an example of POS system


## Pre-requirements 

A. Install [Pyhton](https://www.python.org/downloads/)

B. Install Watchdog lib:
>    pip install watchdog

C. sql lite lib:(Optional)
>    pip install sqlite3


## To setup config file



### A. Access Token    
    1. Create a Facebook Developer Account
    2. Create an App by Clicking on - Create an app >> Business >> Add app name + Select a Business portfolio >> Click Create
    3. Get App Secret by goes into APP settings >> Basic, and copy it.
    4. Get Access Token by going to Tool tab (in the top of screen) >> Access Token Tool (Under "Other Developer Tools")
    5. copy user Token, then from Tool tab select Graph API Explorer >> Add access_token, select the app, select User token under (user or page)
        select permissions (2 WhatsApp selection + Catalog)
        add this code after GET "oauth/access_token?grant_type=fb_exchange_token&client_id={app-id}&client_secret={app-secret}&fb_exchange_token={short-lived-access-token}"
            don't forget to change app-id, app-secret and userToken, and remove these practes {} 

### B. Get WhatsApp Business Account ID:
    1.While logged in to Facebook, open the Business Settings Menu (https://business.facebook.com/settings/).
    2.Under Accounts, select WhatsApp Accounts.
    3.Select your WhatsApp Business Account name.
    4.Under the Company information, you will see the ID at the top-right of the page, in the format of Owned by: Vonage Communication APIs - formerly Nexmo ID: 0000000000000000.
    5.Select the ID number to copy it.

### C. replace path_to_your_database.db with DB Path
