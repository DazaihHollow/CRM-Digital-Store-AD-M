from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
import models
from database import engine, get_db

# Crear tablas (simple auto-migration para inicio)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="CRM Agencia")

# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    total_prospects = db.query(models.Prospect).count()
    contacted_prospects = db.query(models.Prospect).filter(models.Prospect.status == "Contactado").count()
    # Placeholder logic for tasks
    pending_tasks = 0 
    
    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request,
            "title": "Dashboard",
            "active_tab": "dashboard",
            "stats": {
                "total": total_prospects,
                "contacted": contacted_prospects,
                "tasks": pending_tasks
            }
        }
    )

@app.get("/prospectos", response_class=HTMLResponse)
async def prospects_list(request: Request, db: Session = Depends(get_db)):
    prospects = db.query(models.Prospect).all()
    return templates.TemplateResponse(
        "prospects.html", 
        {
            "request": request,
            "title": "Prospectos",
            "active_tab": "prospects",
            "prospects": prospects
        }
    )

@app.post("/prospectos/nuevo")
async def create_prospect(
    name: str = Form(...),
    industry: str = Form(None),
    contact_name: str = Form(None),
    phone: str = Form(None),
    email: str = Form(None),
    db: Session = Depends(get_db)
):
    new_prospect = models.Prospect(
        name=name,
        industry=industry,
        contact_name=contact_name,
        phone=phone,
        email=email
    )
    db.add(new_prospect)
    db.commit()
    return RedirectResponse(url="/prospectos", status_code=303)

@app.get("/planning", response_class=HTMLResponse)
async def planning_view(request: Request):
    return templates.TemplateResponse(
        "planning.html", 
        {
            "request": request,
            "title": "Planificación",
            "active_tab": "planning"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
