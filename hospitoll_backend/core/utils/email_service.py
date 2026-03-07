"""
Email Service for Hospitoll
Handles all email sending functionality
"""

from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Email sending service"""
    
    @staticmethod
    def send_email(
        subject: str,
        recipient_list: list,
        template_name: Optional[str] = None,
        context: Optional[dict] = None,
        plain_text: Optional[str] = None,
        html_content: Optional[str] = None,
        from_email: Optional[str] = None
    ) -> bool:
        """
        Send email with template support
        
        Args:
            subject: Email subject
            recipient_list: List of recipient emails
            template_name: Template file name (optional)
            context: Template context (optional)
            plain_text: Plain text content (optional)
            html_content: HTML content (optional)
            from_email: Sender email (uses DEFAULT_FROM_EMAIL if None)
            
        Returns:
            bool: True if sent successfully
        """
        if not from_email:
            from_email = settings.DEFAULT_FROM_EMAIL
        
        try:
            # If template is provided, render it
            if template_name and context:
                html_content = render_to_string(template_name, context)
            
            # If only plain text, use simple send_mail
            if plain_text and not html_content:
                send_mail(
                    subject=subject,
                    message=plain_text,
                    from_email=from_email,
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                logger.info(f"Email sent to {recipient_list} - Subject: {subject}")
                return True
            
            # If HTML content provided, use EmailMultiAlternatives
            if html_content:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=plain_text or "Ushbu emailni ko'rish uchun HTML ishlayuvchi email kliyentidan foydalaning.",
                    from_email=from_email,
                    to=recipient_list,
                )
                msg.attach_alternative(html_content, "text/html")
                msg.send(fail_silently=False)
                logger.info(f"HTML email sent to {recipient_list} - Subject: {subject}")
                return True
            
            logger.warning(f"Email not sent: No content provided for {recipient_list}")
            return False
            
        except Exception as e:
            logger.error(f"Error sending email to {recipient_list}: {str(e)}")
            return False
    
    @staticmethod
    def send_appointment_reminder(appointment_data: dict) -> bool:
        """
        Send appointment reminder email to patient
        
        Args:
            appointment_data: Dict with appointment details
                - patient_email: str
                - patient_name: str
                - doctor_name: str
                - appointment_date: str
                - appointment_time: str
                - clinic_name: str
                
        Returns:
            bool: True if sent successfully
        """
        subject = f"Randevu eslatmasi - {appointment_data.get('doctor_name')}"
        
        plain_text = f"""
Assalomu alaykim {appointment_data.get('patient_name')},

Sizning {appointment_data.get('appointment_date')} kuni 
{appointment_data.get('appointment_time')} da 
Dr. {appointment_data.get('doctor_name')} bilan randevuingiz bor.

Klinika: {appointment_data.get('clinic_name')}

Agar randevudan voz kechmoqchi bo'lsangiz, iltimos, tez orada uning uchun xabar bering.

Samaryamizdan foydalangan uchun rahmat!
Hospitoll jamiyati
        """
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; direction: rtl;">
                <h2>Randevu Eslatmasi</h2>
                <p>Assalomu alaykim {appointment_data.get('patient_name')},</p>
                
                <p>Sizning randevuingiz:</p>
                <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px;">
                    <p><strong>Doctor:</strong> Dr. {appointment_data.get('doctor_name')}</p>
                    <p><strong>Sana:</strong> {appointment_data.get('appointment_date')}</p>
                    <p><strong>Vaqt:</strong> {appointment_data.get('appointment_time')}</p>
                    <p><strong>Klinika:</strong> {appointment_data.get('clinic_name')}</p>
                </div>
                
                <p style="margin-top: 20px; color: #666;">
                    Agar randevudan voz kechmoqchi bo'lsangiz, iltimos, tez orada uning uchun xabar bering.
                </p>
                
                <p style="margin-top: 30px; color: #999; font-size: 12px;">
                    Samaryamizdan foydalangan uchun rahmat!<br>
                    Hospitoll jamiyati
                </p>
            </body>
        </html>
        """
        
        return EmailService.send_email(
            subject=subject,
            recipient_list=[appointment_data.get('patient_email')],
            plain_text=plain_text,
            html_content=html_content,
        )
    
    @staticmethod
    def send_password_reset(user_email: str, user_name: str, reset_link: str) -> bool:
        """
        Send password reset email
        
        Args:
            user_email: User's email
            user_name: User's full name
            reset_link: Password reset link
            
        Returns:
            bool: True if sent successfully
        """
        subject = "Parol o'zgartirishni qayta talab qiling - Hospitoll"
        
        plain_text = f"""
Assalomu alaykim {user_name},

Siz parol o'zgartirishni talab qildingiz.

Parolni o'zgartirish uchun quyidagi havolani bosing:
{reset_link}

Agar siz bu so'rovni talab qilmagan bo'lsangiz, iltimos, bu emailni e'tibor bemasdan tashlang.

Hospitoll xavfsizlik jamiyati
        """
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; direction: rtl;">
                <h2>Parolni O'zgartirish</h2>
                <p>Assalomu alaykim {user_name},</p>
                
                <p>Siz parol o'zgartirishni talab qildingiz.</p>
                
                <p><a href="{reset_link}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    Parolni O'zgartirish
                </a></p>
                
                <p style="margin-top: 20px; color: #666;">
                    Agar siz bu so'rovni talab qilmagan bo'lsangiz, iltimos, bu emailni e'tibor bemasdan tashlang.
                </p>
                
                <p style="margin-top: 30px; color: #999; font-size: 12px;">
                    Hospitoll xavfsizlik jamiyati
                </p>
            </body>
        </html>
        """
        
        return EmailService.send_email(
            subject=subject,
            recipient_list=[user_email],
            plain_text=plain_text,
            html_content=html_content,
        )
    
    @staticmethod
    def send_subscription_expiry_warning(clinic_email: str, clinic_name: str, days_remaining: int, renewal_link: str) -> bool:
        """
        Send subscription expiry warning email
        
        Args:
            clinic_email: Clinic owner email
            clinic_name: Clinic name
            days_remaining: Days until expiry
            renewal_link: Subscription renewal link
            
        Returns:
            bool: True if sent successfully
        """
        subject = f"⚠️ Obuna muddati tugayotgan - {clinic_name}"
        
        plain_text = f"""
Assalomu alaykim {clinic_name},

Sizning Hospitoll obunаngiz {days_remaining} kun ichida tugaydi.

Xizmatlardan foydalanishni davom ettirish uchun obunaningizni yangilang:
{renewal_link}

Qandaydir savol bo'lsa, biz bilan bog'laning.

Hospitoll jamiyati
        """
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; direction: rtl;">
                <h2>⚠️ Obuna Muddati Tugayotgan</h2>
                <p>Assalomu alaykim {clinic_name},</p>
                
                <p>Sizning Hospitoll obunаngiz <strong>{days_remaining} kun</strong> ichida tugaydi.</p>
                
                <p>Xizmatlardan foydalanishni davom ettirish uchun obunaningizni yangilang:</p>
                <p><a href="{renewal_link}" style="background-color: #FF9800; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    Obunaningizni Yangilash
                </a></p>
                
                <p style="margin-top: 30px; color: #999; font-size: 12px;">
                    Qandaydir savol bo'lsa, biz bilan bog'laning.<br>
                    Hospitoll jamiyati
                </p>
            </body>
        </html>
        """
        
        return EmailService.send_email(
            subject=subject,
            recipient_list=[clinic_email],
            plain_text=plain_text,
            html_content=html_content,
        )
    
    @staticmethod
    def send_invoice_email(recipient_email: str, recipient_name: str, invoice_data: dict) -> bool:
        """
        Send invoice email
        
        Args:
            recipient_email: Recipient's email
            recipient_name: Recipient's name
            invoice_data: Invoice details
                - invoice_number: str
                - amount: float
                - date: str
                - items: list
                
        Returns:
            bool: True if sent successfully
        """
        subject = f"Invoice #{invoice_data.get('invoice_number')} - Hospitoll"
        
        items_html = "".join([
            f"<tr><td>{item['description']}</td><td>{item['quantity']}</td><td>{item['price']:,.0f} so'm</td></tr>"
            for item in invoice_data.get('items', [])
        ])
        
        plain_text = f"""
Assalomu alaykim {recipient_name},

Invoice #{invoice_data.get('invoice_number')} uchun harakat mavjud.

Summa: {invoice_data.get('amount'):,.0f} so'm
Sana: {invoice_data.get('date')}

To'lov qilish uchun quyidagi havolani bosing.

Ospod
        """
        
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; direction: rtl;">
                <h2>Invoice #{invoice_data.get('invoice_number')}</h2>
                <p>Assalomu alaykim {recipient_name},</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background-color: #f5f5f5;">
                        <th style="border: 1px solid #ddd; padding: 10px;">Xizmat</th>
                        <th style="border: 1px solid #ddd; padding: 10px;">Miqdor</th>
                        <th style="border: 1px solid #ddd; padding: 10px;">Narx</th>
                    </tr>
                    {items_html}
                    <tr style="background-color: #f0f0f0; font-weight: bold;">
                        <td colspan="2" style="border: 1px solid #ddd; padding: 10px;">Jami:</td>
                        <td style="border: 1px solid #ddd; padding: 10px;">{invoice_data.get('amount'):,.0f} so'm</td>
                    </tr>
                </table>
                
                <p><a href="{invoice_data.get('payment_link', '#')}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                    To'lov Qilish
                </a></p>
                
                <p style="margin-top: 30px; color: #999; font-size: 12px;">
                    Hospitoll jamiyati
                </p>
            </body>
        </html>
        """
        
        return EmailService.send_email(
            subject=subject,
            recipient_list=[recipient_email],
            plain_text=plain_text,
            html_content=html_content,
        )
