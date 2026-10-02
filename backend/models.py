from sqlalchemy import Column, Integer, String, Text
from database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String, default="Medium")
    status = Column(String, default="Pending")
    location = Column(String, default="Unknown")
    type = Column(String, default="General")
