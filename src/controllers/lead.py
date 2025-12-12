from sqlalchemy.orm import Session
from fastapi import HTTPException
from ..models.lead import Lead
from ..schemas.lead import LeadCreate
from ..models.lead import Lead


def create_lead(db: Session, data: LeadCreate) -> Lead:
    if db.query(Lead).filter(Lead.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email exists")

    # Mapping Logic
    new_lead = Lead(
        # Map Schema 'name' -> Model 'full_name'
        full_name=data.full_name,
        
        # Direct Mappings
        phone_number=data.phone_number,
        email=data.email,
        pan=data.pan,
        gstin=data.gstin,
        
        # Optional fields (will be None if not sent)
        company=data.company,
        annual_revenue=data.annual_revenue,
        city=data.city,
        industry=data.industry,
        description=data.description
    )

    db.add(new_lead)
    db.commit()
    db.refresh(new_lead)
    return new_lead


def get_all_leads(db: Session):
    return db.query(Lead).all()


def update_customer(db: Session, lead_id: int, data: LeadCreate) -> Lead:
    # 1. Find the lead
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # 2. Update fields safely
    lead_data = data.model_dump(exclude_unset=True) # Only get sent fields
    for key, value in lead_data.items():
        setattr(lead, key, value)
        
    # 3. Save
    db.commit()
    db.refresh(lead)
    return lead




# def convert_lead_to_account(db: Session, lead_id: int):
    # 1. Validation: Does the Lead exist?
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    if lead.business_status == "Converted":
        raise HTTPException(status_code=400, detail="Lead is already converted")

    try:
        # 2. Create ACCOUNT (The Business Entity)
        # Logic: If 'company' exists, use it. Otherwise, use the Person's Name.
        account_name = lead.company if lead.company else f"{lead.full_name}'s Account"
        
        new_account = Account(
            name=account_name,
            industry=lead.industry,
            city=lead.city
        )
        db.add(new_account)
        db.flush() # CRITICAL: This generates the 'new_account.id' without finishing the transaction yet

        # 3. Create CONTACT (The Person)
        # Link it to the new_account.id we just generated
        new_contact = Contact(
            account_id=new_account.id, 
            # first_name=lead.full_name.split(" ")[0] if lead.full_name else "",
            # last_name=lead.full_name.split(" ")[-1] if lead.full_name and " " in lead.full_name else "",
            full_name = lead.full_name,
            email=lead.email,
            phone=lead.phone_number
        )
        db.add(new_contact)

        # 4. Update LEAD Status (Archive it)
        lead.business_status = "Converted"

        # 5. Commit Everything
        db.commit()
        db.refresh(new_account)
        
        return {
            "status": "success",
            "message": "Lead converted successfully",
            "account_id": new_account.id,
            "contact_id": new_contact.id
        }

    except Exception as e:
        db.rollback() # Safety Net: If Contact fails, undo the Account creation too
        raise HTTPException(status_code=500, detail=str(e))