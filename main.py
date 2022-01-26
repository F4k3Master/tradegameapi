from lib2to3.pytree import Base
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import pymysql
import requests
import hashlib
from pydantic import BaseModel
import string
import secrets
import datetime

from sqlalchemy import null



class SellRequest(BaseModel):
    quantity: str
    username: str
    stock: str

class StockName(BaseModel):
    stock: str

class TraderToken(BaseModel):
    authToken: str

class TraderName(BaseModel):
    username: str

class TraderInfo(BaseModel):
    username: str
    password: str

class TraderTokenName(BaseModel):
    username: str
    authToken: str

app = FastAPI()
origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


connection = pymysql.connect(host="151.69.121.220",user="leonardo.lucato",passwd="Password2020",database="tradegame")

@app.get("/")
async def root():
    return {"message": "Hello World"}



@app.post("/sellRequest")
async def handleSellRequest(sell_info: SellRequest) :
    available_stock_quantity = await getStockQuantityTrader(sell_info.username,sell_info.stock)
    print(available_stock_quantity)
    if available_stock_quantity < float(sell_info.quantity) :
        if available_stock_quantity > 0:
            return {"result": f"|ERRORE| Hai {available_stock_quantity} azioni di {sell_info.stock} e stai cercando di venderne {sell_info.quantity}! "}
        elif available_stock_quantity == 1:    
            return {"result": f"|ERRORE| Hai 1 azione di {sell_info.stock} e stai cercando di venderne {sell_info.quantity}! "}
        else:
            return {"result": f"|ERRORE| Non hai azioni di {sell_info.stock}!"}    
    return {"result":available_stock_quantity}

async def getStockQuantityTrader(username, stock):
    try:
        connection.connect()
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT quantity FROM active_stock INNER JOIN status ON active_stock.stock_code = status.stock_code WHERE username = '{str(username)}' AND acronym = '{str(stock)}' AND status = 'Open'")
            quantity = float(cursor.fetchone()[0])
            return quantity
    except Exception as e:
        print(e)
        return -1

@app.post("/getTraderActiveStocksCount")
async def getTraderActiveStocksCount(trader_info: TraderName) :
    connection.connect()
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM active_stock INNER JOIN status ON active_stock.stock_code = status.stock_code WHERE username = '{str(trader_info.username)}' AND status = 'Open'")
        n_stocks = str(cursor.fetchone()[0]) 
        return {"n_stocks": n_stocks}

@app.post("/getTraderActiveStocks")
async def getTraderActiveStocks(trader_info: TraderName):
    try: 

        connection.connect()
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT acronym FROM active_stock INNER JOIN status ON active_stock.stock_code = status.stock_code WHERE username = '{str(trader_info.username)}' AND status = 'Open'")
            all_stocks = cursor.fetchall() 
            print(all_stocks)
            return {"result": all_stocks}
    except Exception as e:     
        print(e)   
        return {"result":e}


@app.post("/login")
async def traderLogin(trader_info: TraderInfo):
    if await checkUserPass(trader_info.username,trader_info.password):
        token = await getAuthToken(trader_info.username)
        res = await _validateDateAuthToken(token)
        if res == "Token Expired":
            alphabet = string.ascii_letters + string.digits
            authToken = ''.join(secrets.choice(alphabet) for _ in range(30))
            data = datetime.date.today().strftime("%d/%m/%Y")
            data = str(int(data.split("/")[0])+1) + "/" + data.split("/")[1] + "/" + data.split("/")[2] 
            connection.connect()
            print('TOKEN SCADUTO')
            with connection.cursor() as cursor:
                cursor.execute(f"UPDATE auth_tokens SET auth_token = '{authToken}' WHERE username = '{trader_info.username}'")
                connection.commit()
                cursor.execute(f"UPDATE auth_tokens SET expiration_date = '{data}' WHERE username = '{trader_info.username}'")
                connection.commit()
                print('CREATO NUOVO TOKEN --> ' + authToken)
                return {'authToken':authToken}
        elif res == "Valid Token":     
            print('IL TOKEN E VALIDO QUINDI E UGUALE')
            return {'authToken': token}
        elif res == "No Token":     
            print('NON ESISTE IL TOKEN, NE CREO UNO NUOVO')  
            alphabet = string.ascii_letters + string.digits
            authToken = ''.join(secrets.choice(alphabet) for _ in range(30))
            data = datetime.date.today().strftime("%d/%m/%Y")
            data = str(int(data.split("/")[0])+1) + "/" + data.split("/")[1] + "/" + data.split("/")[2] 
            connection.connect()
            with connection.cursor() as cursor:
                cursor.execute(f"INSERT INTO auth_tokens(username,auth_token,expiration_date) VALUES ('{trader_info.username}','{authToken}','{data}')")
                print('NUOVO TOKEN CREATO  -->  '  + authToken)
                connection.commit()
                return {'authToken':authToken}       
    else:
        return {'authToken': 'null'}

async def _validateDateAuthToken(authToken):
    if authToken == "":
        print('no token')
        return "No Token"
    connection.connect()    
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT expiration_date FROM auth_tokens WHERE auth_token = '{str(authToken)}'")
        date = str(cursor.fetchone()[0])
        expiration_day = int(date.split("/")[0])
        expiration_month = int(date.split("/")[1])
        today_day = datetime.datetime.now().day
        today_month = datetime.datetime.now().month
        if expiration_day <= today_day or expiration_month > today_month:
            return "Token Expired"
        print('valid')    
        return "Valid Token"  

@app.post("/validateDateAuthToken")
async def validateDateAuthToken(traderToken: TraderToken):
    connection.connect()
    if traderToken.authToken == null:
        return {"result":"No Token"}
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT expiration_date FROM auth_tokens WHERE auth_token = '{str(traderToken.authToken)}'")
        date = str(cursor.fetchone()[0])
        expiration_day = int(date.split("/")[0])
        expiration_month = int(date.split("/")[1])
        today_day = datetime.datetime.now().day
        today_month = datetime.datetime.now().month
        if expiration_day <= today_day or expiration_month > today_month:
            return {"result":"Token Expired"} 
        return {"result": "Valid Token"}    

async def getAuthToken(username):
    connection.connect()
    try:
        with connection.cursor() as cursor:
            print('prendo token')
            cursor.execute(f"SELECT auth_token FROM auth_tokens WHERE username = '{str(username)}'")
            token = str(cursor.fetchone()[0])
            if token: return token     
    except:
        return ""


@app.get("/prova")
async def prova():
    return {"ciao":"ciao"}

@app.post("/getTraderBalance")
async def getTraderBalance(trader_name: TraderName):
    connection.connect()
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT balance FROM balance WHERE username = '{str(trader_name.username)}'")
        balance = str(cursor.fetchone()[0])
        return {'balance':balance}

@app.post("/checkAuthToken")      
async def checkAuthToken(trader_name_token: TraderTokenName):
    connection.connect
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT auth_token FROM auth_tokens WHERE username = '{str(trader_name_token.username)}'")
        db_authToken = str(cursor.fetchone()[0])
        if db_authToken == trader_name_token.authToken:
            return {'result':'correct'}
        return {'result':'wrong'}    


async def hashMD5(stuff):
    md5_hash = hashlib.md5()
    md5_hash.update(bytes(stuff.encode('utf-8')))
    return md5_hash.hexdigest()

async def checkUserPass(username,password):
    try:
        connection.connect()
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT password FROM trader WHERE username = '{str(username)}'")
            db_pass = str(cursor.fetchone()[0]).lower()
            if await hashMD5(password) == db_pass:
                return True
            return False     
    except Exception:
        return False    

@app.post("/getStockPrice")
async def getStockPrice(stock_name: StockName):
    print('richiesta di --> ' + stock_name.stock)
    try:
        connection.connect()
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT stock_name FROM stock WHERE acronym = '{str(stock_name.stock)}'")
            full_name = stock_name.stock.lower() + "-" + str(cursor.fetchone()[0]).lower()
            link = f"https://api.coinpaprika.com/v1/tickers/{full_name}?quotes=USD" 
            print(link)
            r = requests.get(link)
            print(float(("{:.7f}".format(r.json()["quotes"]['USD']['price']))))
            return {"result":float(("{:.7f}".format(r.json()["quotes"]['USD']['price'])))}
    except:
        return {"result":-1}
   