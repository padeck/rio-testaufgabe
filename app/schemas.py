from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class TicketCreate(BaseModel):
    request: str = Field(min_length=1, max_length=5000)


class TicketResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticket_id: str = Field(serialization_alias="ticketId")
    category: str
    priority: str
    assigned_team: str = Field(serialization_alias="assignedTeam")
    summary: str
    status: str
    analysis_method: str = Field(serialization_alias="analysisMethod")
    created_at: datetime = Field(serialization_alias="createdAt")

    @classmethod
    def from_orm_ticket(cls, ticket) -> "TicketResponse":
        return cls(
            ticket_id=ticket.ticket_id,
            category=ticket.category,
            priority=ticket.priority,
            assigned_team=ticket.assigned_team,
            summary=ticket.summary,
            status=ticket.status,
            analysis_method=ticket.analysis_method,
            created_at=ticket.created_at,
        )


class TicketListResponse(BaseModel):
    total: int
    tickets: list[TicketResponse]
