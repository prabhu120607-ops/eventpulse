import csv
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from .models import Student, EnrollmentStatus
from .forms import CSVUploadForm, StudentForm
from accounts.models import Department, AuditLog


@login_required
def student_list_view(request):
    query = request.GET.get('q', '').strip()
    dept_id = request.GET.get('dept', '')
    status = request.GET.get('status', '')

    students_qs = Student.objects.select_related('department').all()

    if query:
        students_qs = students_qs.filter(
            Q(full_name__icontains=query) |
            Q(student_number__icontains=query) |
            Q(university_email__icontains=query)
        )
    if dept_id:
        students_qs = students_qs.filter(department_id=dept_id)
    if status:
        students_qs = students_qs.filter(enrollment_status=status)

    paginator = Paginator(students_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'departments': Department.objects.all(),
        'query': query,
        'selected_dept': dept_id,
        'selected_status': status,
        'total_count': students_qs.count(),
    }
    return render(request, 'students/student_list.html', context)


@login_required
def student_import_csv_view(request):
    import_summary = None

    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            default_dept = form.cleaned_data.get('default_department')
            update_existing = form.cleaned_data.get('update_existing')

            try:
                # Read CSV with universal newline support
                decoded_file = csv_file.read().decode('utf-8-sig')
                io_string = io.StringIO(decoded_file)
                reader = csv.reader(io_string)

                # Read header
                raw_header = next(reader, None)
                if not raw_header:
                    messages.error(request, "The uploaded CSV file is empty.")
                    return redirect('students:import_csv')

                # Normalize headers
                header_map = {}
                for idx, col in enumerate(raw_header):
                    norm = col.strip().lower().replace(' ', '_').replace('-', '_')
                    if norm in ['student_number', 'student_id', 'roll_no', 'roll_number', 'id']:
                        header_map['student_number'] = idx
                    elif norm in ['full_name', 'name', 'student_name']:
                        header_map['full_name'] = idx
                    elif norm in ['university_email', 'email', 'student_email']:
                        header_map['email'] = idx
                    elif norm in ['department', 'dept', 'department_code']:
                        header_map['dept'] = idx
                    elif norm in ['academic_year', 'year']:
                        header_map['year'] = idx
                    elif norm in ['section', 'sec']:
                        header_map['section'] = idx

                # Validate essential columns
                missing = []
                for required in ['student_number', 'full_name', 'email']:
                    if required not in header_map:
                        missing.append(required)

                if missing:
                    messages.error(
                        request,
                        f"CSV format error: Missing required column(s): {', '.join(missing)}. "
                        "Please check header row or download the sample CSV template below."
                    )
                    return render(request, 'students/import_csv.html', {'form': form})

                created_count = 0
                updated_count = 0
                skipped_count = 0
                error_rows = []

                for row_idx, row in enumerate(reader, start=2):
                    if not row or not any(row):
                        continue

                    try:
                        s_num = row[header_map['student_number']].strip()
                        name = row[header_map['full_name']].strip()
                        email = row[header_map['email']].strip()

                        if not s_num or not name or not email:
                            error_rows.append({'row': row_idx, 'error': 'Missing student number, name, or email'})
                            skipped_count += 1
                            continue

                        # Validate email
                        validate_email(email)

                        # Department resolution
                        dept = default_dept
                        if 'dept' in header_map and len(row) > header_map['dept']:
                            dept_str = row[header_map['dept']].strip()
                            if dept_str:
                                found_dept = Department.objects.filter(
                                    Q(code__iexact=dept_str) | Q(name__iexact=dept_str)
                                ).first()
                                if found_dept:
                                    dept = found_dept
                                else:
                                    # Create on the fly if needed
                                    dept = Department.objects.create(
                                        name=dept_str,
                                        code=dept_str[:10].upper()
                                    )

                        # Academic Year & Section
                        year = '1st Year'
                        if 'year' in header_map and len(row) > header_map['year']:
                            year_val = row[header_map['year']].strip()
                            if year_val:
                                year = year_val

                        sec = 'A'
                        if 'section' in header_map and len(row) > header_map['section']:
                            sec_val = row[header_map['section']].strip()
                            if sec_val:
                                sec = sec_val

                        # Upsert logic
                        student = Student.objects.filter(Q(student_number=s_num) | Q(university_email=email)).first()
                        if student:
                            if update_existing:
                                student.student_number = s_num
                                student.full_name = name
                                student.university_email = email
                                if dept:
                                    student.department = dept
                                student.academic_year = year
                                student.section = sec
                                student.save()
                                updated_count += 1
                            else:
                                skipped_count += 1
                        else:
                            Student.objects.create(
                                student_number=s_num,
                                full_name=name,
                                university_email=email,
                                department=dept,
                                academic_year=year,
                                section=sec,
                                enrollment_status=EnrollmentStatus.ACTIVE
                            )
                            created_count += 1

                    except ValidationError:
                        error_rows.append({'row': row_idx, 'error': f"Invalid email format: '{email}'"})
                        skipped_count += 1
                    except Exception as ex:
                        error_rows.append({'row': row_idx, 'error': str(ex)})
                        skipped_count += 1

                import_summary = {
                    'created_count': created_count,
                    'updated_count': updated_count,
                    'skipped_count': skipped_count,
                    'error_rows': error_rows,
                }

                AuditLog.objects.create(
                    user=request.user,
                    action='CSV_STUDENT_IMPORT',
                    details=f"Imported CSV roster: {created_count} added, {updated_count} updated, {skipped_count} skipped.",
                    ip_address=request.META.get('REMOTE_ADDR')
                )

                messages.success(
                    request,
                    f"Roster processed: {created_count} students registered, {updated_count} updated, {skipped_count} skipped/errors."
                )

            except Exception as e:
                messages.error(request, f"Failed to process CSV file: {str(e)}")
    else:
        form = CSVUploadForm()

    return render(request, 'students/import_csv.html', {'form': form, 'summary': import_summary})


def download_sample_csv_view(request):
    """
    Provides a standardized sample CSV template for testing student imports.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="eventpulse_sample_students.csv"'

    writer = csv.writer(response)
    writer.writerow(['student_number', 'full_name', 'university_email', 'department', 'academic_year', 'section'])
    writer.writerow(['STU-2024-001', 'Alex Rivera', 'alex.rivera@univ.edu', 'CSE', '3rd Year', 'A'])
    writer.writerow(['STU-2024-002', 'Samantha Chen', 'samantha.chen@univ.edu', 'EEE', '2nd Year', 'B'])
    writer.writerow(['STU-2024-003', 'Rohan Patel', 'rohan.patel@univ.edu', 'ME', '4th Year', 'A'])
    writer.writerow(['STU-2024-004', 'Elena Rostova', 'elena.rostova@univ.edu', 'MBA', 'Postgraduate', '1'])
    writer.writerow(['STU-2024-005', 'Marcus Johnson', 'marcus.j@univ.edu', 'CSE', '1st Year', 'C'])

    return response
