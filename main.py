import json
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
import requests

from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
import os

from models import InvoiceModel

load_dotenv()

app = FastAPI(title="QuickBooks API")
base_url = "https://sandbox-quickbooks.api.intuit.com/"
current_company = None
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

oauth_session = {}

def init_db():
    global oauth_session
    try:
        with open("oauth_session.json", "r") as file:
            oauth_session = json.load(file)
    except FileNotFoundError:
        oauth_session = {}
        with open("oauth_session.json", "w") as file:
            json.dump(oauth_session, file)

init_db()

def get_auth_client():
    """
    Create and return an AuthClient instance using environment variables
    """

    return AuthClient(
        os.getenv("CLIENT_ID"),
        os.getenv("CLIENT_SECRET"),
        os.getenv("REDIRECT_URI"),
        os.getenv("ENVIRONMENT", "sandbox")
    )

def refresh_token():
    """
    Refresh the OAuth token using the refresh token from the session
    """
    global oauth_session
    if 'refresh_token' in oauth_session:
        auth_client = get_auth_client()
        auth_client.refresh(oauth_session.get('refresh_token'))
        oauth_session['access_token'] = auth_client.access_token
        oauth_session['refresh_token'] = auth_client.refresh_token
        oauth_session['token_expiry'] = auth_client.expires_in
        with open("oauth_session.json", "w") as file:
            json.dump(oauth_session, file)
    else:
        raise Exception("No refresh token available")

@app.get("/")
def root():
    """
    Root endpoint that returns a welcome message
    """
    if oauth_session:
        global current_company
        current_company = set_current_company()
        if not current_company:
            refresh_token()
    return {
        "message": "Welcome to QuickBooks API",
        "Company" : current_company if current_company else "No company authenticated"
    }

@app.get("/auth")
def auth():
    """
    Endpoint to redirect to QuickBooks authorization URL
    """
    scopes = [
        Scopes.ACCOUNTING,
    ]
    try:
        auth_client = get_auth_client()
        auth_url = auth_client.get_authorization_url(scopes)

        return RedirectResponse(auth_url, status_code=303)
    except Exception as e:
        return {"error": str(e)}

@app.get("/callback")
def callback(request: Request):
    """
    Callback endpoint to handle QuickBooks authorization response
    """
    try:
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        realm_id = request.query_params.get("realmId")

        if not code or not state:
            return {"error": "Missing code or state parameter"}

        auth_client = get_auth_client()
        auth_client.get_bearer_token(code, realm_id=realm_id)
        oauth_session = {
            "state": state,
            "access_token": auth_client.access_token,
            "refresh_token": auth_client.refresh_token,
            "realm_id": realm_id,
            "token_expiry": auth_client.expires_in
        }
        with open("oauth_session.json", "w") as file:
            json.dump(oauth_session, file)

        return {
            "message": "Authorization successful"
        }
    except Exception as e:
        return {"error": str(e)}

def set_current_company():

    headers.update({
        "Authorization": f"Bearer {oauth_session.get('access_token')}"
    })
    realm_id = oauth_session.get('realm_id')
    try:
        response = requests.get(
            f"{base_url}v3/company/{realm_id}/companyinfo/{realm_id}",
            headers=headers
        )
        if response.status_code == 200:
            return response.json()["CompanyInfo"]["CompanyName"]
        else:
            return None
        
    except Exception as e:
        print(f"Error setting current company: {str(e)}")

@app.get("/customers")
def get_customers():
    """
    Endpoint to fetch customers from QuickBooks
    """
    if not oauth_session:
        return {"error": "Not authenticated"}

    headers.update({
        "Authorization": f"Bearer {oauth_session.get('access_token')}"
    })
    realm_id = oauth_session.get('realm_id')
    params = {
        "query": "Select * from Customer",
    }
    try:
        response = requests.get(
            f"{base_url}v3/company/{realm_id}/query",
            headers=headers,
            params=params
        )
        if response.status_code == 200:
            print("Response:", response.status_code, "Request successful")
            return response.json()["QueryResponse"].get("Customer", [])
        else:
            print("Response:", response.status_code, "Request failed")
            return {"error": "Failed to fetch customers", "status_code": response.status_code}
    except Exception as e:
        print(f"Error fetching customers: {str(e)}")
        return {"error": str(e)}

@app.post("/invoices/create")
def create_invoice(invoice: InvoiceModel):
    """
    Endpoint to create a new invoice in QuickBooks
    """
    if not oauth_session:
        return {"error": "Not authenticated"}

    headers.update({
        "Authorization": f"Bearer {oauth_session.get('access_token')}"
    })
    realm_id = oauth_session.get('realm_id')
    try:
        response = requests.post(
            f"{base_url}v3/company/{realm_id}/invoice",
            headers=headers,
            json=invoice.model_dump()
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": "Failed to create invoice", "status_code": response.status_code}
    except Exception as e:
        print(f"Error creating invoice: {str(e)}")
        return {"error": str(e)}

@app.get("/transactions")
def get_transactions():
    """
    Endpoint to fetch transactions from QuickBooks
    """
    if not oauth_session:
        return {"error": "Not authenticated"}

    headers.update({
        "Authorization": f"Bearer {oauth_session.get('access_token')}"
    })
    realm_id = oauth_session.get('realm_id')
    try:
        response = requests.get(
            f"{base_url}v3/company/{realm_id}/reports/TransactionList",
            headers=headers,
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": "Failed to fetch transactions", "status_code": response.status_code}
    except Exception as e:
        print(f"Error fetching transactions: {str(e)}")
        return {"error": str(e)}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 

