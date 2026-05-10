import requests
import config
import logging

def generate_pix(amount, client_data, identifier):
    """
    Generates a Pix payment using PoseidonPay API.
    
    :param amount: Float value of the transaction.
    :param client_data: Dictionary with 'name', 'email', 'phone', 'document'.
    :param identifier: Unique string for this transaction.
    :return: Dictionary with 'pix_code', 'qr_code_base64', 'transaction_id' or None on failure.
    """
    url = "https://app.poseidonpay.site/api/v1/gateway/pix/receive"
    
    headers = {
        "x-public-key": config.POSEIDON_PUBLIC_KEY,
        "x-secret-key": config.POSEIDON_SECRET_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "identifier": identifier,
        "amount": amount,
        "client": {
            "name": client_data.get('name', 'Cliente Telegram'),
            "email": client_data.get('email'),
            "phone": client_data.get('phone', '11999999999'),
            "document": client_data.get('document')
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json()
        
        if response.status_code in [200, 201]:
            return {
                "pix_code": response_data['pix']['code'],
                "qr_code_base64": response_data['pix'].get('base64'),
                "transaction_id": response_data.get('transactionId') or response_data.get('id')
            }
        else:
            logging.error(f"PoseidonPay API Error (Status {response.status_code}): {response_data}")
            return None
    except Exception as e:
        logging.error(f"Error generating Pix: {e}")
        return None

def check_status(transaction_id):
    """
    Checks the status of a transaction in PoseidonPay.
    As per documentation: GET /gateway/transactions?id={transaction_id}
    """
    url = "https://app.poseidonpay.site/api/v1/gateway/transactions"
    
    headers = {
        "x-public-key": config.POSEIDON_PUBLIC_KEY,
        "x-secret-key": config.POSEIDON_SECRET_KEY,
    }
    
    params = {
        "id": transaction_id
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code in [200, 201]:
            return response.json()
        else:
            logging.error(f"PoseidonPay Status Check Error (Status {response.status_code}): {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error checking status: {e}")
        return None
