from fastapi import FastAPI, Request, Depends, Form, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import timedelta, datetime

import models
import auth
from database import engine, get_db

# NOTA: En producción usar Alembic.
# IMPORTANTE: Ya NO borramos los datos al iniciar.
# models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="CRM Agencia")

# Manejador de errores para redirigir a login en lugar de mostrar JSON
from fastapi.exceptions import HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        return RedirectResponse(url="/login", status_code=303)
    return HTMLResponse(content=f"<h1>Error {exc.status_code}</h1><p>{exc.detail}</p>", status_code=exc.status_code)

# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- RUTAS DE AUTENTICACIÓN ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request, 
    response: Response, 
    username: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Credenciales inválidas"})
    
    access_token = auth.create_access_token(data={"sub": user.username})
    
    # Redirigir al dashboard seteando cookies
    redirect_response = RedirectResponse(url="/", status_code=303)
    redirect_response.set_cookie(key="access_token", value=access_token, httponly=True)
    return redirect_response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):

    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing_user = db.query(models.User).filter(models.User.username == username).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "error": "El usuario ya existe"})
    
    hashed_pwd = auth.get_password_hash(password)
    new_user = models.User(username=username, email=email, hashed_password=hashed_pwd)
    db.add(new_user)
    db.commit()
    
    return RedirectResponse(url="/login", status_code=303)

@app.get("/logout")
async def logout(response: Response):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie("access_token")
    return resp

@app.get("/profile", response_class=HTMLResponse)
async def user_profile(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Traer tareas asignadas
    assigned_tasks = db.query(models.Task).filter(
        models.Task.assignees.any(id=current_user.id)
    ).all()
    
    # Traer Subtareas personales
    my_subtasks = db.query(models.SubTask).filter(models.SubTask.user_id == current_user.id).all()

    return templates.TemplateResponse(
        "profile.html", 
        {
            "request": request,
            "title": "Mi Perfil",
            "active_tab": "profile",
            "user": current_user,
            "tasks": assigned_tasks,
            "subtasks": my_subtasks
        }
    )

# --- Subtareas Endpoints ---
@app.post("/subtasks/create")
async def create_subtask(
    title: str = Form(...),
    task_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    new_sub = models.SubTask(
        title=title,
        task_id=task_id,
        user_id=current_user.id,
        status="todo"
    )
    db.add(new_sub)
    db.commit()
    return RedirectResponse(url="/profile", status_code=303)

@app.post("/subtasks/{sub_id}/update_status")
async def update_subtask_status(
    sub_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    sub = db.query(models.SubTask).filter(models.SubTask.id == sub_id, models.SubTask.user_id == current_user.id).first()
    if sub:
        sub.status = status
        db.commit()
    return RedirectResponse(url="/profile", status_code=303)

@app.post("/subtasks/{sub_id}/delete")
async def delete_subtask(
    sub_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    sub = db.query(models.SubTask).filter(models.SubTask.id == sub_id, models.SubTask.user_id == current_user.id).first()
    if sub:
        db.delete(sub)
        db.commit()
    return RedirectResponse(url="/profile", status_code=303)

@app.post("/profile/update")
async def update_profile(
    email: str = Form(None),
    password: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    if email:
        current_user.email = email
    if password:
        current_user.hashed_password = auth.get_password_hash(password)
        
    db.commit()
    return RedirectResponse(url="/profile", status_code=303)


# --- RUTAS PROTEGIDAS ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    total_prospects = db.query(models.Prospect).count()
    contacted_prospects = db.query(models.Prospect).filter(models.Prospect.status == "Contactado").count()
    
    # Tareas asignadas AL USUARIO actual que están pendientes
    my_pending_tasks = db.query(models.Task).filter(
        models.Task.assignees.any(id=current_user.id),
        models.Task.status != models.TaskStatus.DONE
    ).count()
    
    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request,
            "title": "Dashboard",
            "active_tab": "dashboard",
            "user": current_user,
            "stats": {
                "total": total_prospects,
                "contacted": contacted_prospects,
                "tasks": my_pending_tasks
            }
        }
    )

@app.get("/prospectos", response_class=HTMLResponse)
async def prospects_list(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    prospects = db.query(models.Prospect).all()
    return templates.TemplateResponse(
        "prospects.html", 
        {
            "request": request,
            "title": "Prospectos",
            "active_tab": "prospects",
            "user": current_user,
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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    new_prospect = models.Prospect(
        name=name,
        industry=industry,
        contact_name=contact_name,
        phone=phone,
        email=email,
        created_by_id=current_user.id # Asignamos creador
    )
    db.add(new_prospect)
    db.commit()
    return RedirectResponse(url="/prospectos", status_code=303)

@app.get("/prospectos/{prospect_id}", response_class=HTMLResponse)
async def prospect_detail(
    request: Request, 
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    prospect = db.query(models.Prospect).filter(models.Prospect.id == prospect_id).first()
    if not prospect:
        # Podríamos retornar un 404 custom
        return RedirectResponse(url="/prospectos")
    
    # Necesitamos usuarios para el modal de nueva tarea
    users = db.query(models.User).all()
        
    return templates.TemplateResponse(
        "prospect_detail.html", 
        {
            "request": request,
            "title": f"{prospect.name} - Detalle",
            "active_tab": "prospects",
            "user": current_user,
            "prospect": prospect,
            "users": users
        }
    )

@app.post("/prospectos/{prospect_id}/update")
async def update_prospect(
    prospect_id: int,
    name: str = Form(...),
    industry: str = Form(None),
    status: str = Form(...),
    contact_name: str = Form(None),
    phone: str = Form(None),
    email: str = Form(None),
    address: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    prospect = db.query(models.Prospect).filter(models.Prospect.id == prospect_id).first()
    if prospect:
        prospect.name = name
        prospect.industry = industry
        prospect.status = status
        prospect.contact_name = contact_name
        prospect.phone = phone
        prospect.email = email
        prospect.address = address
        db.commit()
    
    return RedirectResponse(url=f"/prospectos/{prospect_id}", status_code=303)

@app.post("/prospectos/{prospect_id}/delete")
async def delete_prospect(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    prospect = db.query(models.Prospect).filter(models.Prospect.id == prospect_id).first()
    if prospect:
        db.delete(prospect)
        db.commit()
    return RedirectResponse(url="/prospectos", status_code=303)

@app.get("/planning", response_class=HTMLResponse)
async def planning_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Obtener tareas agrupadas o filtrarlas en frontend
    # Para simplicidad, traemos todas y el template filtra, o filtramos aquí
    tasks = db.query(models.Task).all()
    prospects = db.query(models.Prospect).all() # Para el select de crear tarea
    users = db.query(models.User).all() # Para asignar
    
    return templates.TemplateResponse(
        "planning.html", 
        {
            "request": request,
            "title": "Planificación",
            "active_tab": "planning",
            "user": current_user,
            "tasks": tasks,
            "prospects": prospects,
            "users": users,
            "TaskStatus": models.TaskStatus
        }
    )

@app.get("/calendar", response_class=HTMLResponse)
async def calendar_view(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Traer tareas que tengan fecha de fin para mostrarlas
    tasks = db.query(models.Task).filter(models.Task.end_date != None).all()
    return templates.TemplateResponse(
        "calendar.html", 
        {
            "request": request,
            "title": "Calendario",
            "active_tab": "calendar",
            "user": current_user,
            "tasks_with_dates": tasks
        }
    )

@app.post("/tasks/create")
async def create_task(
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    prospect_id: int = Form(None),
    start_date: str = Form(None), # Recibimos como string "YYYY-MM-DD"
    end_date: str = Form(None),
    assignee_ids: list[int] = Form([]),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    # Convertir fechas si existen
    start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None

    new_task = models.Task(
        title=title,
        description=description,
        prospect_id=prospect_id,
        status=models.TaskStatus.TODO,
        start_date=start_dt,
        end_date=end_dt
    )
    
    if assignee_ids:
        assignees = db.query(models.User).filter(models.User.id.in_(assignee_ids)).all()
        new_task.assignees = assignees
        
    db.add(new_task)
    db.commit()
    # Redirigir a la página desde donde se llamó (referer) o default a planning
    referer = request.headers.get("referer")
    if referer:
        return RedirectResponse(url=referer, status_code=303)
    return RedirectResponse(url="/planning", status_code=303)

@app.post("/tasks/{task_id}/delete")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()
    return RedirectResponse(url="/planning", status_code=303)

@app.post("/tasks/{task_id}/update_status")
async def update_task_status(
    request: Request,
    task_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        task.status = status
        db.commit()
    # Redirigir al referer para que sirva desde planning y prospect detail
    referer = request.headers.get("referer") or "/planning"
    return RedirectResponse(url=referer, status_code=303)

@app.post("/tasks/{task_id}/update")
async def update_task_details(
    request: Request,
    task_id: int,
    title: str = Form(...),
    description: str = Form(None),
    start_date: str = Form(None),
    end_date: str = Form(None),
    assignee_ids: list[int] = Form([]),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_active_user)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task:
        task.title = title
        task.description = description
        task.start_date = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
        task.end_date = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
        
        # Actualizar asignados
        # Si assignee_ids viene vacío, ¿significa borrar todos o que no se envió?
        # En HTML forms, un select multiple vacío no envía nada. 
        # Asumiremos que si la clave existe (incluso vacía) en el form data es intencional, 
        # pero FastAPI Form([]) maneja esto. 
        # Para simplificar: Siempre reemplazamos con lo que llegue.
        if assignee_ids:
             new_assignees = db.query(models.User).filter(models.User.id.in_(assignee_ids)).all()
             task.assignees = new_assignees
        else:
             # Si llega vacío, limpiamos (desasignar a todos)
             task.assignees = []

        db.commit()
        
    referer = request.headers.get("referer") or "/planning"
    return RedirectResponse(url=referer, status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
