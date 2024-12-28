import uvicorn
from fastapi import FastAPI
from route import health

app = FastAPI(
    title= "Choon Autotrade Batch",
    description="This is a project for batch processing in Choon Autotrade.",
    version="1.0.0"
)

app.include_router(health.router)

# if __name__ == "__main__":
#     uvicorn.run(
#         "main:app",
#         host=settings.HOST,
#         port=settings.PORT,
#         reload=True
#     )