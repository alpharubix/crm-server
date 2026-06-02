import logging
import os
import smtplib
import time  # For throttling requests to avoid Zoho blocks
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# Single Source of Truth for Sender info to prevent domain spoofing errors
SENDER_EMAIL = "suraj.gupta@r1xchange.com"
SENDER_DISPLAY = "R1xchange CRM Mail Service"


def create_smtp_connection():
    try:
        smtp = smtplib.SMTP_SSL("smtp.zoho.in", 465, timeout=10)
        smtp.ehlo()
        app_password = os.getenv("APP_PASSWORD")

        if not app_password:
            print("Error: APP_PASSWORD environment variable is not set.")
            return None

        smtp.login(SENDER_EMAIL, app_password)
        print("SMTP connection created successfully.")
        return smtp
    except Exception as e:
        print("Error creating SMTP connection:", e)
        return None


def prepare_mail_body(module_name, parent_id, user_name, note):
    html_content = f"""
        <p>Dear User,</p>
        <p>You have been mentioned in a note. Please review the details below:</p>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
        <tr><td><strong>Module</strong></td><td>{module_name}</td></tr>
        <tr><td><strong>Link to see the note</strong></td><td>https://r1xchange-crm.vercel.app/{module_name}/{parent_id}</td></tr>
        <tr><td><strong>Mentioned By user</strong></td><td>{user_name}</td></tr>
        <tr><td><strong>Note</strong></td><td>{note}</td></tr>
        </table>
        <p>Please log in to the CRM system to take necessary action.</p>
        <p>Regards,<br>R1xchange CRM SERVER</p>
    """
    return html_content


def process_mention_emails(email_list):
    ready_emails = []
    for email in email_list:
        mail = {
            "email_address": email.get("user_email_address"),
            "body": prepare_mail_body(
                module_name=email.get("module"),
                parent_id=email.get("entity_id"),
                user_name=email.get("user_name"),
                note=email.get("note"),
            ),
        }
        ready_emails.append(mail)
    send_comments_email(ready_emails)


def send_comments_email(email_list):
    smtp = create_smtp_connection()
    if not smtp:
        print("Aborting send_comments_email: SMTP connection failed.")
        return

    try:
        for email in email_list:
            msg = MIMEMultipart()
            msg["From"] = f"{SENDER_DISPLAY} <{SENDER_EMAIL}>"
            msg["To"] = email["email_address"]
            msg["Subject"] = "You were mentioned in a note"
            msg.attach(MIMEText(email["body"], "html"))

            try:
                smtp.send_message(msg)
                print(f"Email sent successfully to {email['email_address']}")
                time.sleep(1.5)  # Anti-blocking delay
            except Exception as e:
                print(f"Error sending email to {email['email_address']}: {e}")
    finally:
        try:
            smtp.quit()
        except:
            print("Error in send_comments_email")
            pass


def send_general_email_list(to, subject, body):
    """The core engine that handles both single emails or lists of emails smoothly."""
    smtp = create_smtp_connection()
    if not smtp:
        print("SMTP connection could not be established")
        return None

    try:
        # If 'to' is a single string string like "prathap@r1xchange.com",
        # this safely converts it into ["prathap@r1xchange.com"]
        recipients = to if isinstance(to, list) else [to]

        for email in recipients:
            msg = MIMEMultipart()
            msg["From"] = f"{SENDER_DISPLAY} <{SENDER_EMAIL}>"
            msg["To"] = email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html"))

            try:
                smtp.send_message(msg)
                print(f"Email sent successfully to {email}")
                time.sleep(1.5)  # Anti-blocking delay for Zoho
            except Exception as e:
                print(f"Error sending email to {email}: {e}")
    except Exception as e:
        print("SMTP connection failed:", e)
    finally:
        try:
            smtp.quit()
        except:
            print("Error in send_general_email_list")
            pass
    return None


def send_general_email(to: str, subject: str, body: str):
    """
    Restored for backwards compatibility with the export controllers.
    It passes the arguments to the safer list-based controller seamlessly.
    """
    return send_general_email_list(to=to, subject=subject, body=body)


def notify_account_created(
    owner_email: str,
    owner_name: str,
    account_name: str,
    account_id: int,
    account_status: str,
    account_stage: str,
    created_by_name: str,
):
    html = f"""
    <p>Dear {owner_name},</p>
    <p>A new account has been created and assigned to you. Please find the details below:</p>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
      <tr><td><strong>Account Name</strong></td><td>{account_name}</td></tr>
      <tr><td><strong>Account ID</strong></td><td>{account_id}</td></tr>
      <tr><td><strong>Status</strong></td><td>{account_status or "N/A"}</td></tr>
      <tr><td><strong>Stage</strong></td><td>{account_stage or "N/A"}</td></tr>
      <tr><td><strong>Created By</strong></td><td>{created_by_name}</td></tr>
      <tr><td><strong>View Account</strong></td><td><a href="https://r1xchange-crm.vercel.app/accounts/{account_id}">Open in CRM</a></td></tr>
    </table>
    <p>Please log in to the CRM to take any necessary action.</p>
    <p>Regards,<br>R1xchange CRM</p>
    """
    # Consolidated everything to use the list utility cleanly
    send_general_email_list(
        to=owner_email, subject=f"New Account Assigned: {account_name}", body=html
    )


def notify_project_created(
    approver_email: str, approver_name: str, project_name: str, project_id: int
):
    html = f"""
    <p>Dear {approver_name},</p>
    <p>A new project has been created: "<strong>{project_name}</strong>"</p>
    <p>Kindly review and approve the project.</p>
    <p><a href="https://r1xchange-crm.vercel.app/projects/{project_id}">Open Project</a></p>
    <p>Thanks,<br>Data Administrator</p>
    """
    send_general_email_list(
        to=approver_email,
        subject=f"Project Approval Required: {project_name}",
        body=html,
    )


def notify_project_approved(emails: list, project_name: str, project_id: int):
    html = f"""
    <p>Dear All,</p>
    <p>The project "<strong>{project_name}</strong>" is approved and assigned to you.</p>
    <p>Kindly begin work on the project.</p>
    <p><a href="https://r1xchange-crm.vercel.app/projects/{project_id}">Open Project</a></p>
    <p>Thanks,<br>Data Administrator</p>
    """
    send_general_email_list(
        to=emails, subject=f"Project Approved: {project_name}", body=html
    )


def notify_project_overdue(
    emails: list, project_name: str, project_id: int, overdue_days: int
):
    html = f"""
    <p>Dear Team,</p>
    <p>This is an automated system reminder that the project "<strong>{project_name}</strong>" is currently overdue by <span style="color: red; font-weight: bold;">{overdue_days}</span> days.</p>
    
    <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin: 15px 0;">
        <strong>Reminder Note:</strong> Please prioritize your pending tasks immediately, update your progress, and move this project forward for administrative review.
    </div>
    
    <p><a href="https://r1xchange-crm.vercel.app/projects/{project_id}" style="background-color: #007bff; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; display: inline-block;">Open Project Workspace</a></p>
    <br>
    <p>Thanks,<br>Data Administrator</p>
    """
    send_general_email_list(
        to=emails,
        subject=f"[Overdue Warning] Action Required: {project_name} (+{overdue_days} Days)",
        body=html,
    )


def notify_project_pending_review(
    approver_email: str, approver_name: str, project_name: str, project_id: int
):
    html = f"""
    <p>Dear {approver_name},</p>
    <p>The project "<strong>{project_name}</strong>" has been moved to <strong>Pending Review</strong>.</p>
    <p>Kindly review the project.</p>
    <p><a href="https://r1xchange-crm.vercel.app/projects/{project_id}">Open Project</a></p>
    <p>Thanks,<br>Data Administrator</p>
    """
    send_general_email_list(
        to=[approver_email, "subhasini.ts@r1xchange.com"],
        subject=f"Project Pending Review: {project_name}",
        body=html,
    )


def notify_project_completed(emails: list, project_name: str, project_id: int):
    html = f"""
    <p>Dear All,</p>
    <p>Great news! The project "<strong>{project_name}</strong>" has been marked as <strong>Completed</strong>.</p>
    <p>Thank you for your hard work and contribution to finishing this project successfully.</p>
    <p><a href="https://r1xchange-crm.vercel.app/projects/{project_id}">View Completed Project</a></p>
    <p>Regards,<br>R1xchange CRM</p>
    """
    send_general_email_list(
        to=emails, subject=f"Project Completed: {project_name}", body=html
    )


def notify_account_assigned(
    recipients_list: list, owner_name: str, account_name: str, account_id: int
):
    """
    Sends the official assignment notification alert to the
    Account Owner and their corresponding Reporting Manager.
    """
    html = f"""
    <p>Dear {owner_name},</p>
    
    <p>A new record under the module "<strong>Accounts</strong>" for "<strong>{account_name}</strong>" has been assigned to you via CRM system, please do login into the system and check for the details.</p>
    
    <p><a href="https://r1xchange-crm.vercel.app/accounts/{account_id}" style="background-color: #28a745; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; display: inline-block;">Open Assigned Account</a></p>
    
    <br/>
    <p>Thanks,</p>
    <p><strong>CRM Data Administrator</strong></p>
    <p style="color: gray; font-size: 11px;">This is an automated system message. Please do not reply directly.</p>
    """

    send_general_email_list(
        to=recipients_list, subject=f"New Account Assigned: {account_name}", body=html
    )


def notify_deal_created_approval(
    recipients_list: list, account_name: str, deal_id: int
):
    """
    Sends an approval request alert to the Reporting Manager and
    the Banking Team whenever a single new Deal record is created.
    """
    html = f"""
    <p>Dear Banking Team / Reporting Manager,</p>
    
    <p>A new Deal is created under the "<strong>{account_name}</strong>", Kindly review the request and provide approval for lender login.</p>
    
    <p><a href="https://r1xchange-crm.vercel.app/deals/{deal_id}" style="background-color: #007bff; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; display: inline-block;">Review Deal Profile</a></p>
    
    <br/>
    <p>Thanks,</p>
    <p><strong>CRM Data Administrator</strong></p>
    <p style="color: gray; font-size: 11px;">This is an automated system message. Please do not reply directly to this email.</p>
    """

    send_general_email_list(
        to=recipients_list,
        subject=f"New Deal Created - Approval Required: {account_name}",
        body=html,
    )


def notify_ticket_created(emails: list, account_name: str, ticket_id: int):
    html = f"""
    <p>Dear Deal Owner / Reporting Manager,</p>
    <p>A new Ticket is created under the "<strong>{account_name}</strong>" module and has been assigned to the Ticket Owner.</p>
    <p><a href="https://r1xchange-crm.vercel.app/tickets/{ticket_id}" style="background-color: #007bff; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; display: inline-block;">Open Ticket Profile</a></p>
    <br/>
    <p>Thanks,</p>
    <p><strong>CRM Data Administrator</strong></p>
    """
    send_general_email_list(
        to=emails, subject=f"New Ticket Created: {account_name}", body=html
    )


def notify_ticket_approved(emails: list, lender_name: str, ticket_id: int):
    html = f"""
    <p>Dear Deal Owner / Reporting Manager,</p>
    <p>Your ticket created has been <strong>Approved</strong> by the banking team and will be logged with lender: <strong>{lender_name or "N/A"}</strong>.</p>
    <p><a href="https://r1xchange-crm.vercel.app/tickets/{ticket_id}" style="background-color: #28a745; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; display: inline-block;">View Approved Ticket</a></p>
    <br/>
    <p>Thanks,</p>
    <p><strong>CRM Data Administrator</strong></p>
    """
    send_general_email_list(to=emails, subject="Ticket - Approved", body=html)


def notify_ticket_disapproved(emails: list, lender_name: str, ticket_id: int):
    html = f"""
    <p>Dear Deal Owner / Reporting Manager,</p>
    <p>Your ticket created has been <strong style="color: red;">Disapproved</strong> by the banking team and will be logged with lender: <strong>{lender_name or "N/A"}</strong>.</p>
    <p><a href="https://r1xchange-crm.vercel.app/tickets/{ticket_id}" style="background-color: #dc3545; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; display: inline-block;">View Ticket Details</a></p>
    <br/>
    <p>Thanks,</p>
    <p><strong>CRM Data Administrator</strong></p>
    """
    send_general_email_list(to=emails, subject="Ticket - Disapproved", body=html)


def notify_document_submitted(
    emails: list, deal_name: str, module_name: str, doc_id: int
):
    html = f"""
    <p>Dear Banking Team / Reporting Manager,</p>
    <p>A new document has been <strong>submitted</strong> under the Deal "<strong>{deal_name}</strong>" under the Module "<strong>{module_name or "N/A"}</strong>".</p>
    <p><a href="https://r1xchange-crm.vercel.app/deals/documents/{doc_id}" style="background-color: #28a745; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; display: inline-block;">Review Submitted Document</a></p>
    <br/>
    <p>Thanks,</p>
    <p><strong>CRM Data Administrator</strong></p>
    """
    send_general_email_list(
        to=emails, subject=f"Document submitted - {deal_name}", body=html
    )


def notify_document_required(
    emails: list, deal_name: str, module_name: str, doc_id: int
):
    html = f"""
    <p>Dear Deal Owner,</p>
    <p>A new document is <strong>required</strong> under the Deal "<strong>{deal_name}</strong>" under the Module "<strong>{module_name or "N/A"}</strong>". Please login to upload the requested asset.</p>
    <p><a href="https://r1xchange-crm.vercel.app/deals/documents/{doc_id}" style="background-color: #dc3545; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; display: inline-block;">View Requested Document</a></p>
    <br/>
    <p>Thanks,</p>
    <p><strong>CRM Data Administrator</strong></p>
    """
    send_general_email_list(
        to=emails, subject=f"Document Required - {deal_name}", body=html
    )
