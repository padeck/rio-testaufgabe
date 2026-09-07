import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ai_service
from app.database import get_db, init_db, ping_db
from app.models import Ticket
from app.schemas import TicketCreate, TicketListResponse, TicketResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Support Ticket AI", version="1.0.0", lifespan=lifespan)


def _new_ticket_id() -> str:
    return f"T-{secrets.token_hex(3)}"


@app.get("/health")
def health():
    if not ping_db():
        raise HTTPException(status_code=503, detail="database unreachable")
    return {"status": "ok"}


@app.post("/api/tickets", response_model=TicketResponse, status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    result = ai_service.analyze(payload.request)
    status = ai_service.compute_status(result.category, result.priority)

    ticket = Ticket(
        ticket_id=_new_ticket_id(),
        request_text=payload.request,
        category=result.category,
        priority=result.priority,
        assigned_team=result.assigned_team,
        summary=result.summary,
        status=status,
        analysis_method=result.analysis_method,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    logger.info(
        "ticket created id=%s category=%s priority=%s method=%s status=%s",
        ticket.ticket_id, ticket.category, ticket.priority, ticket.analysis_method, ticket.status,
    )
    return TicketResponse.from_orm_ticket(ticket)


@app.get("/api/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    ticket = db.scalar(select(Ticket).where(Ticket.ticket_id == ticket_id))
    if ticket is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return TicketResponse.from_orm_ticket(ticket)


@app.get("/api/tickets", response_model=TicketListResponse)
def list_tickets(status: str | None = Query(default=None), db: Session = Depends(get_db)):
    stmt = select(Ticket).order_by(Ticket.created_at.desc())
    if status:
        stmt = stmt.where(Ticket.status == status)
    tickets = db.scalars(stmt).all()
    return TicketListResponse(
        total=len(tickets),
        tickets=[TicketResponse.from_orm_ticket(t) for t in tickets],
    )
