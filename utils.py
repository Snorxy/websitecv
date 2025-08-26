"""
Utility functions untuk website operations
"""
import re
import phonenumbers
from typing import List, Optional, Tuple

def clean_phone_number(phone: str) -> Optional[str]:
    """Clean dan standardize phone number dengan auto-detection negara"""
    if not phone:
        return None
    
    try:
        # Remove extra spaces and characters
        phone = re.sub(r'[^\d+]', '', phone.strip())
        
        if not phone:
            return None
        
        # Jika sudah ada + di awal, coba parse langsung
        if phone.startswith('+'):
            try:
                parsed = phonenumbers.parse(phone, None)
                if phonenumbers.is_valid_number(parsed):
                    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            except:
                pass
        
        # Jika tidak ada +, coba parse langsung dengan + di awal (mungkin sudah lengkap dengan country code)
        if not phone.startswith('+') and len(phone) >= 8:
            try:
                test_phone = f'+{phone}'
                parsed = phonenumbers.parse(test_phone, None)
                if phonenumbers.is_valid_number(parsed):
                    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            except:
                pass
        
        # List negara untuk auto-detection (diperluas untuk semua negara utama)
        country_codes = [
            # Asia Pacific
            "ID", "MY", "SG", "TH", "PH", "VN", "JP", "KR", "CN", "IN", "PK", "BD", "AU", "NZ",
            # Europe  
            "GB", "DE", "FR", "IT", "ES", "NL", "BE", "CH", "AT", "SE", "NO", "DK", "FI", "PL", "RU", "TR",
            # North America
            "US", "CA", "MX",
            # South America
            "BR", "AR", "CL", "CO", "PE", "VE",
            # Africa
            "ZA", "EG", "NG", "KE", "MA",
            # Middle East
            "SA", "AE", "IL", "IR", "IQ", "JO", "LB", "KW", "QA", "BH", "OM"
        ]
        
        # Coba parse dengan berbagai region (fallback)
        for region in country_codes:
            try:
                parsed = phonenumbers.parse(phone, region)
                if phonenumbers.is_valid_number(parsed):
                    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            except:
                continue
        
        # Manual handling untuk format umum hanya untuk nomor lokal (dimulai 0)
        if phone.startswith('0') and len(phone) >= 10:
            # Nomor lokal, coba berbagai country code (diperluas)
            common_codes = [
                '62',   # Indonesia
                '60',   # Malaysia  
                '65',   # Singapore
                '66',   # Thailand
                '63',   # Philippines
                '84',   # Vietnam
                '81',   # Japan
                '82',   # South Korea
                '86',   # China
                '91',   # India
                '1',    # US/Canada
                '44',   # UK
                '49',   # Germany
                '33',   # France
                '39',   # Italy
                '34',   # Spain
                '31',   # Netherlands
                '41',   # Switzerland
                '46',   # Sweden
                '47',   # Norway
                '45',   # Denmark
                '48',   # Poland
                '7',    # Russia
                '55',   # Brazil
                '54',   # Argentina
                '56',   # Chile
                '57',   # Colombia
                '51',   # Peru
                '58',   # Venezuela
                '27',   # South Africa
                '20',   # Egypt
                '234',  # Nigeria
                '254',  # Kenya
                '212',  # Morocco
                '966',  # Saudi Arabia
                '971',  # UAE
                '972',  # Israel
                '98',   # Iran
                '964',  # Iraq
                '962',  # Jordan
                '961',  # Lebanon
                '965',  # Kuwait
                '974',  # Qatar
                '973',  # Bahrain
                '968'   # Oman
            ]
            for code in common_codes:
                try:
                    test_phone = f'+{code}{phone[1:]}'
                    parsed = phonenumbers.parse(test_phone, None)
                    if phonenumbers.is_valid_number(parsed):
                        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                except:
                    continue
        
        # Jika tidak ada +, coba deteksi dari panjang dan pattern
        if not phone.startswith('+') and len(phone) >= 8:
            # Special handling untuk nomor yang dimulai dengan 1 (US/Canada format tanpa +)
            if phone.startswith('1') and len(phone) >= 10:
                try:
                    test_phone = f'+{phone}'
                    parsed = phonenumbers.parse(test_phone, None)
                    if phonenumbers.is_valid_number(parsed):
                        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                except:
                    pass
            
            # Coba parse langsung dengan + di awal (mungkin sudah lengkap dengan country code)
            try:
                test_phone = f'+{phone}'
                parsed = phonenumbers.parse(test_phone, None)
                if phonenumbers.is_valid_number(parsed):
                    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            except:
                pass
            
            # Pattern detection berdasarkan panjang nomor (hanya jika parsing langsung gagal)
            if phone.startswith('0') and len(phone) >= 10:
                # Nomor lokal, coba berbagai country code (gunakan list yang sama)
                common_codes = [
                    '62', '60', '65', '66', '63', '84', '81', '82', '86', '91',
                    '1', '44', '49', '33', '39', '34', '31', '41', '46', '47',
                    '45', '48', '7', '55', '54', '56', '57', '51', '58', '27',
                    '20', '234', '254', '212', '966', '971', '972', '98', '964',
                    '962', '961', '965', '974', '973', '968'
                ]
                for code in common_codes:
                    try:
                        test_phone = f'+{code}{phone[1:]}'
                        parsed = phonenumbers.parse(test_phone, None)
                        if phonenumbers.is_valid_number(parsed):
                            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                    except:
                        continue
            
            # Special handling untuk nomor yang dimulai dengan angka tertentu (tanpa leading 0)
            # Coba deteksi berdasarkan panjang dan pattern umum
            if len(phone) >= 10:
                # Untuk nomor 10-11 digit yang dimulai dengan 1 (kemungkinan US/Canada)
                if phone.startswith('1') and len(phone) in [10, 11]:
                    try:
                        test_phone = f'+{phone}'
                        parsed = phonenumbers.parse(test_phone, None)
                        if phonenumbers.is_valid_number(parsed):
                            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                    except:
                        pass
                
                # Untuk nomor panjang lainnya, coba berbagai country code
                common_long_codes = ['86', '91', '7', '81', '82', '49', '33', '39', '34']
                for code in common_long_codes:
                    try:
                        test_phone = f'+{code}{phone}'
                        parsed = phonenumbers.parse(test_phone, None)
                        if phonenumbers.is_valid_number(parsed):
                            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                    except:
                        continue
        
        # Terakhir, return original jika valid format
        if len(phone.replace('+', '')) >= 8:
            return phone if phone.startswith('+') else f'+{phone}'
        
        return None
    except Exception as e:
        print(f"Error cleaning phone number {phone}: {e}")
        return None

def parse_txt_to_vcf(content: str, name_prefix: str = '') -> List[str]:
    """Parse TXT content dan convert ke VCF format"""
    try:
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        if not lines:
            return []
        
        # Calculate padding for line numbers
        total_lines = len(lines)
        padding = max(2, len(str(total_lines)))  # Minimal 2 digit
        
        vcf_contacts = []
        
        for line_num, line in enumerate(lines, 1):
            name = None
            phone = None
            
            # Parse different formats
            if ',' in line:
                # Format: Nama,Nomor
                parts = line.split(',', 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    phone = clean_phone_number(parts[1].strip())
            elif ';' in line:
                # Format: Nama;Nomor
                parts = line.split(';', 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    phone = clean_phone_number(parts[1].strip())
            elif ':' in line:
                # Format: Nama: Nomor
                parts = line.split(':', 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    phone = clean_phone_number(parts[1].strip())
            elif '-' in line and any(char.isdigit() for char in line):
                # Format: Nama - Nomor
                parts = line.split('-', 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    phone = clean_phone_number(parts[1].strip())
            else:
                # Try to extract phone number from line
                phone_pattern = r'[+0-9][0-9+\s\-()]{6,}'
                matches = re.findall(phone_pattern, line)
                for candidate in matches or [line]:
                    candidate = candidate.strip()
                    cleaned_phone = clean_phone_number(candidate)
                    if cleaned_phone:
                        phone = cleaned_phone
                        # Use line number as name if no name found
                        padded_num = str(line_num).zfill(padding)
                        name = f"Contact {padded_num}"
                        break
            
            # Generate VCF entry if we have valid phone
            if phone and len(phone.replace('+', '')) >= 8:
                if not name:
                    padded_num = str(line_num).zfill(padding)
                    name = f"Contact {padded_num}"
                
                # Apply name prefix if provided
                if name_prefix:
                    if name.startswith('Contact'):
                        # For auto-generated names, replace "Contact" with prefix
                        padded_num = str(line_num).zfill(padding)
                        name = f"{name_prefix} {padded_num}"
                    else:
                        # For parsed names, add prefix
                        name = f"{name_prefix} {name}"
                
                # Clean name
                name = re.sub(r'[^\w\s]', '', name).strip()
                if not name:
                    padded_num = str(line_num).zfill(padding)
                    name = f"Contact {padded_num}"
                
                vcf_entry = f"""BEGIN:VCARD
VERSION:3.0
FN:{name}
N:{name};;;;
TEL:{phone}
END:VCARD"""
                vcf_contacts.append(vcf_entry)
        
        return vcf_contacts
        
    except Exception as e:
        print(f"Error parsing TXT to VCF: {e}")
        return []

def split_txt_file(content: str, chunk_size: int) -> List[str]:
    """Split TXT file content menjadi chunks"""
    try:
        lines = content.split('\n')
        
        if not lines:
            return []
        
        chunks = []
        
        for i in range(0, len(lines), chunk_size):
            chunk_lines = lines[i:i + chunk_size]
            chunk_content = '\n'.join(chunk_lines)
            chunks.append(chunk_content)
        
        return chunks
        
    except Exception as e:
        print(f"Error splitting TXT file: {e}")
        return []

def validate_txt_format(content: str) -> Tuple[bool, str, dict]:
    """Validate TXT file format dan return statistics"""
    try:
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        if not lines:
            return False, "File kosong", {}
        
        valid_contacts = 0
        total_lines = len(lines)
        detected_formats = []
        
        for line in lines:
            if ',' in line:
                detected_formats.append('comma')
                parts = line.split(',', 1)
                if len(parts) == 2:
                    phone = clean_phone_number(parts[1].strip())
                    if phone:
                        valid_contacts += 1
            elif ';' in line:
                detected_formats.append('semicolon')
                parts = line.split(';', 1)
                if len(parts) == 2:
                    phone = clean_phone_number(parts[1].strip())
                    if phone:
                        valid_contacts += 1
            elif ':' in line:
                detected_formats.append('colon')
                parts = line.split(':', 1)
                if len(parts) == 2:
                    phone = clean_phone_number(parts[1].strip())
                    if phone:
                        valid_contacts += 1
            else:
                # Try to extract phone number
                phone_pattern = r'[+0-9][0-9+\s\-()]{6,}'
                matches = re.findall(phone_pattern, line)
                for candidate in matches or [line]:
                    phone = clean_phone_number(candidate.strip())
                    if phone:
                        detected_formats.append('phone_only')
                        valid_contacts += 1
                        break
        
        stats = {
            'total_lines': total_lines,
            'valid_contacts': valid_contacts,
            'success_rate': (valid_contacts / total_lines * 100) if total_lines > 0 else 0,
            'detected_formats': list(set(detected_formats))
        }
        
        if valid_contacts == 0:
            return False, "Tidak ada nomor telepon valid ditemukan", stats
        elif valid_contacts < total_lines * 0.5:
            return True, f"Peringatan: Hanya {valid_contacts}/{total_lines} kontak valid ditemukan", stats
        else:
            return True, f"Format valid: {valid_contacts}/{total_lines} kontak ditemukan", stats
            
    except Exception as e:
        return False, f"Error validating format: {str(e)}", {}

def format_file_size(size_bytes: int) -> str:
    """Format file size dalam human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def parse_vcf_to_txt(content: str, output_format: str = 'comma') -> List[str]:
    """Parse VCF content dan convert ke TXT format"""
    try:
        # Split content by VCARD entries
        vcards = content.split('BEGIN:VCARD')
        contacts = []
        
        for vcard in vcards:
            if not vcard.strip():
                continue
                
            # Extract name and phone
            name = None
            phone = None
            
            lines = vcard.split('\n')
            for line in lines:
                line = line.strip()
                
                # Extract name (FN or N field)
                if line.startswith('FN:'):
                    name = line[3:].strip()
                elif line.startswith('N:') and not name:
                    n_parts = line[2:].split(';')
                    if n_parts[0]:
                        name = n_parts[0].strip()
                
                # Extract phone number
                elif line.startswith('TEL:') or line.startswith('TEL;'):
                    # Handle different TEL formats
                    if ':' in line:
                        phone = line.split(':', 1)[1].strip()
                    
            # Clean and validate data
            if name and phone:
                # Clean name
                name = re.sub(r'[^\w\s]', '', name).strip()
                if not name:
                    name = "Unknown"
                    
                # Clean phone  
                phone = clean_phone_number(phone)
                
                if phone:
                    # Format output based on preference
                    if output_format == 'comma':
                        contacts.append(f"{name},{phone}")
                    elif output_format == 'semicolon':
                        contacts.append(f"{name};{phone}")
                    elif output_format == 'colon':
                        contacts.append(f"{name}: {phone}")
                    elif output_format == 'dash':
                        contacts.append(f"{name} - {phone}")
                    elif output_format == 'space':
                        contacts.append(f"{name} {phone}")
                    elif output_format == 'phone_only':
                        # HANYA NOMOR TELEPON TANPA NAMA DAN TANPA +
                        phone_clean = phone.replace('+', '') if phone.startswith('+') else phone
                        contacts.append(phone_clean)
                    else:
                        contacts.append(f"{name},{phone}")  # Default to comma
        
        return contacts
        
    except Exception as e:
        print(f"Error parsing VCF to TXT: {e}")
        return []


def parse_admin_navy_to_vcf(admin_numbers: str, navy_numbers: str, admin_contact_name: str = 'Admin', navy_contact_name: str = 'Navy') -> List[str]:
    """Parse admin and navy phone numbers and convert to VCF format with sequential naming"""
    try:
        vcf_contacts = []
        
        # Process admin numbers
        if admin_numbers.strip():
            admin_lines = [line.strip() for line in admin_numbers.split('\n') if line.strip()]
            # Calculate padding for admin numbers
            total_admin = len(admin_lines)
            padding = max(2, len(str(total_admin)))  # Minimal 2 digit
            
            for i, line in enumerate(admin_lines, 1):
                # Clean phone number
                phone = clean_phone_number(line)
                if phone and len(phone.replace('+', '')) >= 8:
                    contact_number = str(i).zfill(padding)
                    contact_name = f"{admin_contact_name} {contact_number}"
                    
                    vcf_entry = f"""BEGIN:VCARD
VERSION:3.0
FN:{contact_name}
N:{contact_name};;;;
TEL:{phone}
END:VCARD"""
                    vcf_contacts.append(vcf_entry)
        
        # Process navy numbers
        if navy_numbers.strip():
            navy_lines = [line.strip() for line in navy_numbers.split('\n') if line.strip()]
            # Calculate padding for navy numbers
            total_navy = len(navy_lines)
            padding = max(2, len(str(total_navy)))  # Minimal 2 digit
            
            for i, line in enumerate(navy_lines, 1):
                # Clean phone number
                phone = clean_phone_number(line)
                if phone and len(phone.replace('+', '')) >= 8:
                    contact_number = str(i).zfill(padding)
                    contact_name = f"{navy_contact_name} {contact_number}"
                    
                    vcf_entry = f"""BEGIN:VCARD
VERSION:3.0
FN:{contact_name}
N:{contact_name};;;;
TEL:{phone}
END:VCARD"""
                    vcf_contacts.append(vcf_entry)
        
        return vcf_contacts
        
    except Exception as e:
        print(f"Error parsing admin/navy to VCF: {e}")
        return []

def parse_admin_navy_to_vcf_with_start(admin_numbers: str, navy_numbers: str, 
                                     admin_name_prefix: str = 'Admin', navy_name_prefix: str = 'Navy',
                                     admin_start_number: int = 1, navy_start_number: int = 1) -> List[str]:
    """Parse admin and navy phone numbers with custom start numbers and convert to VCF format"""
    try:
        vcf_contacts = []
        
        # Process admin numbers
        if admin_numbers.strip():
            admin_lines = [line.strip() for line in admin_numbers.split('\n') if line.strip()]
            # Calculate padding needed based on total number of contacts
            total_admin = len(admin_lines)
            max_number = admin_start_number + total_admin - 1
            padding = max(2, len(str(max_number)))  # Minimal 2 digit
            
            for i, line in enumerate(admin_lines):
                # Clean phone number
                phone = clean_phone_number(line)
                if phone and len(phone.replace('+', '')) >= 8:
                    contact_number = str(admin_start_number + i).zfill(padding)
                    contact_name = f"{admin_name_prefix} {contact_number}"
                    
                    vcf_entry = f"""BEGIN:VCARD
VERSION:3.0
FN:{contact_name}
N:{contact_name};;;;
TEL:{phone}
END:VCARD"""
                    vcf_contacts.append(vcf_entry)
        
        # Process navy numbers
        if navy_numbers.strip():
            navy_lines = [line.strip() for line in navy_numbers.split('\n') if line.strip()]
            # Calculate padding needed based on total number of contacts
            total_navy = len(navy_lines)
            max_number = navy_start_number + total_navy - 1
            padding = max(2, len(str(max_number)))  # Minimal 2 digit
            
            for i, line in enumerate(navy_lines):
                # Clean phone number
                phone = clean_phone_number(line)
                if phone and len(phone.replace('+', '')) >= 8:
                    contact_number = str(navy_start_number + i).zfill(padding)
                    contact_name = f"{navy_name_prefix} {contact_number}"
                    
                    vcf_entry = f"""BEGIN:VCARD
VERSION:3.0
FN:{contact_name}
N:{contact_name};;;;
TEL:{phone}
END:VCARD"""
                    vcf_contacts.append(vcf_entry)
        
        return vcf_contacts
        
    except Exception as e:
        print(f"Error parsing admin/navy to VCF with start numbers: {e}")
        return []

def merge_vcf_files(vcf_contents_list: List[str], contact_name_prefix: str = 'Gabung') -> List[str]:
    """Merge multiple VCF file contents into one with sequential naming - Optimized"""
    try:
        merged_vcf_contacts = []
        contact_counter = 1
        
        # First pass: count total contacts to calculate padding
        total_contacts = 0
        for vcf_content in vcf_contents_list:
            if vcf_content.strip():
                import re
                total_contacts += len(re.findall(r'BEGIN:VCARD', vcf_content))
        
        # Calculate padding
        padding = max(2, len(str(total_contacts)))  # Minimal 2 digit
        
        for vcf_content in vcf_contents_list:
            if not vcf_content.strip():
                continue
            
            # Optimized: Use regex to find all VCARD blocks at once
            import re
            vcard_pattern = r'BEGIN:VCARD(.*?)END:VCARD'
            vcards = re.findall(vcard_pattern, vcf_content, re.DOTALL)
            
            for vcard_content in vcards:
                # Optimized: Use regex to extract phone number directly
                tel_pattern = r'TEL[^:]*:([^\r\n]+)'
                tel_match = re.search(tel_pattern, vcard_content)
                
                if tel_match:
                    phone = tel_match.group(1).strip()
                    
                    # Quick clean phone number (simplified for speed)
                    cleaned_phone = ''.join(filter(str.isdigit, phone))
                    if len(cleaned_phone) >= 10:  # Basic validation
                        # Add + if not present and looks like international
                        if not phone.startswith('+') and len(cleaned_phone) > 10:
                            cleaned_phone = '+' + cleaned_phone
                        elif phone.startswith('+'):
                            cleaned_phone = '+' + cleaned_phone
                        else:
                            cleaned_phone = phone  # Keep original format
                        
                        contact_number = str(contact_counter).zfill(padding)
                        contact_name = f"{contact_name_prefix} {contact_number}"
                        
                        # Optimized: Direct string formatting
                        vcf_entry = f"BEGIN:VCARD\nVERSION:3.0\nFN:{contact_name}\nN:{contact_name};;;;\nTEL:{cleaned_phone}\nEND:VCARD"
                        merged_vcf_contacts.append(vcf_entry)
                        contact_counter += 1
        
        return merged_vcf_contacts
        
    except Exception as e:
        print(f"Error merging VCF files: {e}")
        return []

def analyze_vcf_file(content: str) -> dict:
    """Analyze VCF file and return statistics - Optimized"""
    try:
        import re
        
        # Quick count using regex
        vcard_count = len(re.findall(r'BEGIN:VCARD', content))
        
        # Quick phone extraction for preview (first 5 only)
        tel_pattern = r'TEL[^:]*:([^\r\n]+)'
        tel_matches = re.findall(tel_pattern, content)
        
        # Quick preview without full parsing
        preview_contacts = []
        for i, phone in enumerate(tel_matches[:5]):
            phone_clean = ''.join(filter(str.isdigit, phone.strip()))
            if len(phone_clean) >= 10:
                preview_contacts.append(phone.strip())
        
        return {
            'total_contacts': len(tel_matches),
            'total_vcards': vcard_count,
            'preview': preview_contacts,
            'has_valid_contacts': len(tel_matches) > 0
        }
        
    except Exception as e:
        print(f"Error analyzing VCF file: {e}")
        return {
            'total_contacts': 0,
            'total_vcards': 0,
            'preview': [],
            'has_valid_contacts': False
        }
