import asyncio
import json
import base64
import httpx
import os
from flask import Flask, request, jsonify
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf import json_format
import FreeFire_pb2

app = Flask(__name__)

# ============================================================
# 🚨 SIRF YAHAN LIMIT BADLO 🚨
LIMIT = 4000
# ============================================================

REGION          = "IND"
RELEASE_VERSION = "OB52"
USER_AGENT      = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
MAIN_KEY        = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
MAIN_IV         = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')
TOKENS_FILE     = "/tmp/tokens.json"
UIDPASS_FILE    = "uidpass.json"

# ── CRYPTO HELPERS ───────────────────────────────────────────

def _pad(data: bytes) -> bytes:
    pad_len = AES.block_size - (len(data) % AES.block_size)
    return data + bytes([pad_len] * pad_len)

def aes_encrypt_proto(plaintext: bytes) -> bytes:
    cipher = AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV)
    return cipher.encrypt(_pad(plaintext))

def encrypt_api(hex_str: str) -> bytes:
    cipher = AES.new(MAIN_KEY, AES.MODE_CBC, MAIN_IV)
    return cipher.encrypt(pad(bytes.fromhex(hex_str), AES.block_size))

def Encrypt_ID(number) -> str:
    try:
        number = int(number)
        encoded_bytes = []
        while True:
            byte = number & 0x7F
            number >>= 7
            if number:
                byte |= 0x80
            encoded_bytes.append(byte)
            if not number:
                break
        return bytes(encoded_bytes).hex()
    except Exception:
        return ""

def get_sender_uid(token: str) -> int:
    try:
        payload = token.split('.')[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        data = json.loads(base64.b64decode(payload).decode('utf-8'))
        uid = data.get("external_uid") or data.get("account_id")
        return int(uid)
    except Exception:
        return 0

def game_headers(token: str, region: str) -> dict:
    return {
        "Host": f"client.{region.lower()}.freefiremobile.com",
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "gzip",
        "Authorization": f"Bearer {token}",
        "X-GA": "v1 1",
        "ReleaseVersion": RELEASE_VERSION,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.11f1",
        "Connection": "Keep-Alive",
    }

# ── TOKEN GENERATION (uidpass.json → tokens.json) ────────────

async def fetch_access_token(uid: str, password: str) -> tuple:
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = (
        f"uid={uid}&password={password}"
        "&response_type=token&client_type=2"
        "&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
        "&client_id=100067"
    )
    headers = {"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, data=payload, headers=headers)
        data = resp.json()
    return data.get("access_token", ""), data.get("open_id", "")

async def fetch_jwt_for_account(acc: dict):
    access_token, open_id = await fetch_access_token(acc['uid'], acc['password'])
    if not access_token:
        return None

    login_req = FreeFire_pb2.LoginReq()
    json_format.ParseDict({
        "open_id": open_id,
        "open_id_type": "4",
        "login_token": access_token,
        "orign_platform_type": "4",
    }, login_req)
    encrypted = aes_encrypt_proto(login_req.SerializeToString())

    headers = {
        "User-Agent": USER_AGENT,
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/octet-stream",
        "Expect": "100-continue",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": RELEASE_VERSION,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post("https://loginbp.ggblueshark.com/MajorLogin", data=encrypted, headers=headers)

    login_res = FreeFire_pb2.LoginRes()
    login_res.ParseFromString(resp.content)
    msg = json.loads(json_format.MessageToJson(login_res))
    token = msg.get("token", "")
    return {"token": token} if token else None

async def generate_tokens() -> list:
    try:
        with open(UIDPASS_FILE, "r") as f:
            accs = json.load(f)[:LIMIT]
    except Exception:
        return []

    sem = asyncio.Semaphore(50)
    results = []

    async def process(acc):
        async with sem:
            t = await fetch_jwt_for_account(acc)
            if t:
                results.append(t)

    await asyncio.gather(*(process(acc) for acc in accs))

    # /tmp mein save karo
    with open(TOKENS_FILE, "w") as f:
        json.dump(results, f)

    return results

def load_tokens() -> list:
    try:
        with open(TOKENS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

# ── VISIT / ADDFRIEND ────────────────────────────────────────

async def do_visit(client, token: str, target_uid, region: str) -> bool:
    url = f"https://client.{region.lower()}.freefiremobile.com/GetPlayerPersonalShow"
    try:
        payload = encrypt_api(f"08{Encrypt_ID(target_uid)}1007")
        r = await client.post(url, headers=game_headers(token, region), content=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

async def do_addfriend(client, token: str, target_uid, region: str) -> bool:
    url = f"https://client.{region.lower()}.freefiremobile.com/RequestAddingFriend"
    try:
        sender_uid = get_sender_uid(token)
        if not sender_uid:
            return False
        payload = encrypt_api(f"08{Encrypt_ID(sender_uid)}10{Encrypt_ID(target_uid)}1801")
        r = await client.post(url, headers=game_headers(token, region), content=payload, timeout=10)
        return r.status_code == 200
    except Exception:
        return False

async def run_bulk(target_uid, action: str, limit: int, region: str) -> dict:
    tokens = load_tokens()
    if not tokens:
        # tokens nahi mile toh pehle refresh karo
        tokens = await generate_tokens()
    if not tokens:
        return {"error": "Tokens available nahi hain. /refresh call karo."}

    sem = asyncio.Semaphore(50)

    async def bounded(td):
        async with sem:
            t = td.get("token", "")
            if action == "visit":
                return await do_visit(client, t, target_uid, region)
            elif action == "add":
                return await do_addfriend(client, t, target_uid, region)
            return False

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(bounded(td) for td in tokens[:limit]))

    return {
        "status": "success",
        "action": action,
        "target_uid": target_uid,
        "region": region,
        "accounts_tried": len(results),
        "successful_requests": results.count(True),
    }

# ── FLASK ROUTES ─────────────────────────────────────────────

@app.route('/')
def home():
    token_count = len(load_tokens())
    return jsonify({
        "msg": "Visit Bot Running!",
        "limit": LIMIT,
        "tokens_cached": token_count
    }), 200

# 🔴 Cron job (vercel.json) har 6 ghante yahan aayega
@app.route('/refresh')
async def refresh_endpoint():
    tokens = await generate_tokens()
    return jsonify({
        "status": "success",
        "msg": f"uidpass.json se {len(tokens)} tokens generate aur save ho gaye"
    }), 200

@app.route('/visit', methods=['GET'])
async def visit_endpoint():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "UID zaruri hai"}), 400
    limit = int(request.args.get('limit', LIMIT))
    region = request.args.get('server_name', request.args.get('region', REGION))
    region = region.replace('(', '').replace(')', '').strip().upper()
    result = await run_bulk(uid, "visit", limit, region)
    return jsonify(result), 200

@app.route('/addfriend', methods=['GET'])
async def addfriend_endpoint():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "UID zaruri hai"}), 400
    limit = int(request.args.get('limit', LIMIT))
    region = request.args.get('server_name', request.args.get('region', REGION))
    region = region.replace('(', '').replace(')', '').strip().upper()
    result = await run_bulk(uid, "add", limit, region)
    return jsonify(result), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
