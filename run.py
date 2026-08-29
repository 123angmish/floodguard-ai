import uvicorn
import os

if __name__ == "__main__":
    print("=" * 65)
    print("🌊 STARTING FLOODGUARD AI 2.0 APPLICATION SERVER")
    print("=" * 65)
    print("• Web Dashboard:  http://127.0.0.1:8000")
    print("• Swagger Docs:   http://127.0.0.1:8000/docs")
    print("• Sample Video:   t4.mp4 (Auto-loaded in Demo Mode)")
    print("=" * 65)
    
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
