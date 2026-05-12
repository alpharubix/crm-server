import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from src.config import settings
import logging

logger = logging.getLogger(__name__)


def create_smtp_connection():
    try:
            smtp = smtplib.SMTP('smtp.zoho.com', 587, timeout=10)
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            app_password = settings.APP_PASSWORD
            print(app_password)
            smtp.login('techmgr@meramerchant.com', app_password)
            print("SMTP connection created successfully.")
            return smtp
    except Exception as e:
        print("Error creating SMTP connection:", e)
        return None


def prepare_mail_body(module_name, parent_id,user_name,note):

        html_content = f"""
        <p>Dear User,</p>
        
        <p>You have been mentioned in a note. Please review the details below:</p>
        
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse;">
        <tr>
        <td><strong>Module</strong></td>
        <td>{module_name}</td>
        </tr>
        
        <tr>
        <td><strong>Link to see the note</strong></td>
        <td>https://r1xchange-crm.netlify.app/{module_name}/{parent_id}</td>
        </tr>
        
        <tr>
        <td><strong>Mentioned By user</strong></td>
        <td>{user_name}</td>
        </tr>
        
        <tr>
        <td><strong>Note</strong></td>
        <td>{note}</td>
        </tr>
        </table>
        
        <p>Please log in to the CRM system to take necessary action.</p>
        
        <p>Regards,<br>
        R1xchange CRM SERVER</p>
        """

        return html_content


def process_mention_emails(email_list):
    ready_emails = []
    for email in email_list:
        mail = {"email_address":email.get('user_email_address'),"body":prepare_mail_body(module_name=email.get('module'),parent_id=email.get('entity_id'),user_name=email.get('user_name'),note=email.get('note'))}
        ready_emails.append(mail)
    send_comments_email(ready_emails)
    return None


def send_comments_email(email_list):
        try:
            smtp = create_smtp_connection()
            for email in email_list:
                msg = MIMEMultipart()

                msg['From'] = "R1xchange Crm mail service <techmgr@meramerchant.com>"
                msg['To'] = email["email_address"]
                msg['Subject'] = "You were mentioned in a note"

                msg.attach(MIMEText(email["body"], 'html'))
                try:
                    smtp.send_message(msg)
                    print(f"Email sent successfully to {email['email_address']}")
                except Exception as e:
                    print(f"Error sending email to {email['email_address']}:", e)

            smtp.quit()
            return None

        except Exception as e:
            print("SMTP connection failed:", e)
            return None



def send_general_email(to, subject, body):
    try:
        smtp = create_smtp_connection()
        msg = MIMEMultipart()
        msg['From'] = "R1xchange CRM Mail Service <techmgr@meramerchant.com>"
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        smtp.send_message(msg)
        smtp.quit()
        print(f"Email sent successfully to {to}")
    except Exception as e:
            print(f"Error sending email to {to['email_address']}:", e)
            return None

def send_general_email_list(to, subject, body):

    smtp = create_smtp_connection()

    if not smtp:
        print("SMTP connection could not be established")
        return None

    try:

        # convert single email into list
        recipients = to if isinstance(to, list) else [to]

        for email in recipients:

            msg = MIMEMultipart()

            msg['From'] = "R1xchange CRM Mail Service <techmgr@meramerchant.com>"
            msg['To'] = email
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html'))

            try:
                smtp.send_message(msg)
                print(f"Email sent successfully to {email}")

            except Exception as e:
                print(f"Error sending email to {email}: {e}")

    except Exception as e:
        print("SMTP connection failed:", e)

    finally:
        try:
            smtp.quit()
        except Exception:
            pass

    return None

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
      <tr><td><strong>Status</strong></td><td>{account_status or 'N/A'}</td></tr>
      <tr><td><strong>Stage</strong></td><td>{account_stage or 'N/A'}</td></tr>
      <tr><td><strong>Created By</strong></td><td>{created_by_name}</td></tr>
      <tr>
        <td><strong>View Account</strong></td>
        <td><a href="https://r1xchange-crm.netlify.app/accounts/{account_id}">Open in CRM</a></td>
      </tr>
    </table>

    <p>Please log in to the CRM to take any necessary action.</p>

    <p>Regards,<br>R1xchange CRM</p>
    """
    send_general_email(
        to=owner_email,
        subject=f"New Account Assigned: {account_name}",
        body=html,
    )

def notify_project_created(
    approver_email: str,
    approver_name: str,
    project_name: str,
    project_id: int,
):
    html = f"""
    <p>Dear {approver_name},</p>

    <p>
        A new project has been created:
        "<strong>{project_name}</strong>"
    </p>

    <p>
        Kindly review and approve the project.
    </p>

    <p>
        <a href="https://r1xchange-crm.netlify.app/projects/{project_id}">
            Open Project
        </a>
    </p>

    <p>
        Thanks,<br>
        Data Administrator
    </p>
    """

    send_general_email_list(
        to=approver_email,
        subject=f"Project Approval Required: {project_name}",
        body=html,
    )



def notify_project_approved(
    emails: list,
    project_name: str,
    project_id: int,
):
    html = f"""
    <p>Dear All,</p>

    <p>
        The project "<strong>{project_name}</strong>"
        is approved and assigned to you.
    </p>

    <p>
        Kindly begin work on the project.
    </p>

    <p>
        <a href="https://r1xchange-crm.netlify.app/projects/{project_id}">
            Open Project
        </a>
    </p>

    <p>
        Thanks,<br>
        Data Administrator
    </p>
    """

    send_general_email_list(
        to=emails,
        subject=f"Project Approved: {project_name}",
        body=html,
    )



def notify_project_overdue(
    emails: list,
    project_name: str,
    project_id: int,
    overdue_days: int,
):
    html = f"""
    <p>Dear All,</p>

    <p>
        This is a reminder that the project
        "<strong>{project_name}</strong>"
        is overdue by <strong>{overdue_days}</strong> days.
    </p>

    <p>
        Kindly prioritize and complete the pending tasks
        and move the project for review.
    </p>

    <p>
        <a href="https://r1xchange-crm.netlify.app/projects/{project_id}">
            Open Project
        </a>
    </p>

    <p>
        Thanks,<br>
        Data Administrator
    </p>
    """

    send_general_email_list(
        to=emails,
        subject=f"Project Overdue Reminder: {project_name}",
        body=html,
    )


def notify_project_pending_review(
    approver_email: str,
    approver_name: str,
    project_name: str,
    project_id: int,
):
    html = f"""
    <p>Dear {approver_name},</p>

    <p>
        The project "<strong>{project_name}</strong>"
        has been moved to <strong>Pending Review</strong>.
    </p>

    <p>
        Kindly review the project.
    </p>

    <p>
        <a href="https://r1xchange-crm.netlify.app/projects/{project_id}">
            Open Project
        </a>
    </p>

    <p>
        Thanks,<br>
        Data Administrator
    </p>
    """

    send_general_email_list(
        to=approver_email,
        subject=f"Project Pending Review: {project_name}",
        body=html,
    )