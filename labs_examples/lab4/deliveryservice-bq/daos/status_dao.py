from sqlalchemy import Column, String, Integer, TIMESTAMP

from db import Base


class StatusDAO(Base):
    __tablename__ = 'status'

    id = Column(Integer, primary_key=True)  # Auto generated primary key
    status_name = Column(String)
    last_update = Column(TIMESTAMP(timezone=False))

    def __init__(self, sid, status, last_update):
        self.id = sid
        self.status_name = status
        self.last_update = last_update
