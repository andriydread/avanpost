import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("app.server:app", host="127.0.0.1", port=port, reload=True)
