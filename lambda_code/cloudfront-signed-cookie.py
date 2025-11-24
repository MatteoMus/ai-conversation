import json
import time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from base64 import b64encode
import boto3
import os

client_ssm = boto3.client('ssm')
private_key_ssm = os.getenv('PRIVATE_KEY_SSM')
resource_url = f"https://{os.getenv('CLOUDFRONT_DOMAIN')}/*"
expiration = int(time.time()) + os.getenv('COOKIE_EXPIRATION', '86400')  # Default to 24 hours
key_pair_id = os.getenv('KEY_PAIR_ID')
auth_user = os.getenv('AUTH_USER')
auth_pass = os.getenv('AUTH_PASS')

def load_private_key():
    response = client_ssm.get_parameter(
        Name=private_key_ssm,
        WithDecryption=True
    )
    private_key = serialization.load_pem_private_key(
        response['Parameter']['Value'].encode('utf-8'), 
        password=None)
    
    return private_key

def create_policy(resource_url, expiration):
    policy = {
        "Statement": [
            {
                "Resource": resource_url,
                "Condition": {
                    "DateLessThan": {
                        "AWS:EpochTime": expiration
                    }
                }
            }
        ]
    }
    return json.dumps(policy)

def sign_policy(policy, private_key):
    signature = private_key.sign(
        policy.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA1()
    )
    return b64encode(signature).decode('utf-8')

def set_signed_cookie():
    private_key = load_private_key()
    policy = create_policy(resource_url, expiration)
    signature = sign_policy(policy, private_key)

    return {
        "status": "302",
        "statusDescription": 'Found',
        "headers": {
            "location": [{
                "key": 'Location',
                "value": "/",
            }],
            'cache-control': [{
                "key": "Cache-Control",
                "value": "no-cache, no-store, must-revalidate"
            }],
            'set-cookie': [{
                "key": "Set-Cookie",
                "value": f"CloudFront-Policy={b64encode(policy.encode('utf-8')).decode('utf-8')}"
            }, {
                "key": "Set-Cookie",
                "value": f"CloudFront-Key-Pair-Id={key_pair_id}"
            }, {
                "key": "Set-Cookie",
                "value": f"CloudFront-Signature={signature}"
            }]
        }
    }

def ask_login():
    return {
        "status": "401",
        "statusDescription": 'Unauthorized',
        "headers": {
            "www-authenticate": [{
                "key": 'WWW-Authenticate',
                "value": 'Basic'
            }]
        }
    }

def lambda_handler(event, context):
    print("event received")
    print(event)

    authUser = auth_user
    authPass = auth_pass
    authString = authUser + ":" + authPass
    authString = f"Basic {b64encode(authString.encode('ascii')).decode('utf-8')}"
    print(authString)
    request_headers = event["Records"][0]["cf"]["request"]["headers"]

    if "authorization" in request_headers:
        if request_headers["authorization"][0]["value"] == authString:
            print("authorized")
            return set_signed_cookie()
        else:
            print("unauthorized")
            return ask_login()
    else:
        print("unauthorized")
        return ask_login()

    #return set_signed_cookie()

