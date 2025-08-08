from django.shortcuts import render, redirect
from .models import MissingPerson, Location  # Make sure Location is imported
from django.contrib import messages
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from datetime import datetime
import face_recognition
import cv2
import geocoder  # Import geocoder for location tracking
from django.conf import settings
from django.utils import timezone  # For accurate timestamp

# Create your views here.
def home(request):
    return render(request, "index.html")


def capture_video():
    # Initialize video capture
    video_capture = cv2.VideoCapture(0)

    # Set video codec and create VideoWriter object to save the video
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    video_filename = "captured_video.avi"
    video_writer = cv2.VideoWriter(video_filename, fourcc, 20.0, (640, 480))

    # Record 3 seconds of video
    start_time = cv2.getTickCount()
    while int(cv2.getTickCount() - start_time) / cv2.getTickFrequency() < 3:  # 3 seconds
        ret, frame = video_capture.read()
        if ret:
            video_writer.write(frame)

    video_capture.release()
    video_writer.release()

    return video_filename


def send_email_with_video(subject, context, recipient_email, video_file_path, is_case_registered=False):
    from_email = 'pptodo01@gmail.com'  # Use a valid email address
    if is_case_registered:
        html_message = render_to_string('casefile.html', context)  # For case registration
    else:
        html_message = render_to_string('findemail.html', context)  # For person detection

    # Create the email
    email = EmailMessage(subject, '', from_email, [recipient_email])

    # Attach the video file
    if video_file_path:
        with open(video_file_path, 'rb') as video_file:
            email.attach('captured_video.avi', video_file.read(), 'video/avi')

    # Attach HTML message
    email.content_subtype = "html"
    email.body = html_message

    email.send(fail_silently=False)
    print(f"Email sent to {recipient_email} with video attachment")


def detect(request):
    video_capture = cv2.VideoCapture(0)

    # Initialize face detection flag
    face_detected = False

    while True:
        ret, frame = video_capture.read()

        # Find face locations and encodings in the current frame
        face_locations = face_recognition.face_locations(frame)
        face_encodings = face_recognition.face_encodings(frame, face_locations)

        for face_encoding, (top, right, bottom, left) in zip(face_encodings, face_locations):
            for person in MissingPerson.objects.all():
                stored_image = face_recognition.load_image_file(person.image.path)
                stored_face_encoding = face_recognition.face_encodings(stored_image)[0]

                matches = face_recognition.compare_faces([stored_face_encoding], face_encoding)

                if any(matches):
                    name = f"{person.first_name} {person.last_name}"
                    cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)
                    font = cv2.FONT_HERSHEY_DUPLEX
                    cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)

                    # Check if a face has already been detected
                    if not face_detected:
                        print(f"Found {name}")

                        # Get geolocation (latitude and longitude) using IP address
                        g = geocoder.ip('me')  # Get the location based on IP
                        current_latitude = g.latlng[0] if g.latlng else None
                        current_longitude = g.latlng[1] if g.latlng else None

                        # Store location in the database if geolocation is available
                        if current_latitude and current_longitude:
                            Location.objects.create(
                                missing_person=person,
                                latitude=current_latitude,
                                longitude=current_longitude,
                                detected_at=timezone.now()  # Timestamp for the location detection
                            )
                            print(f"Location stored for {name}: Latitude {current_latitude}, Longitude {current_longitude}")

                        # Prepare email content
                        current_time = datetime.now().strftime('%d-%m-%Y %H:%M')
                        subject = 'Missing Person Found'
                        recipient_email = person.email
                        context = {
                            "first_name": person.first_name,
                            "last_name": person.last_name,
                            "fathers_name": person.father_name,
                            "aadhar_number": person.aadhar_number,
                            "missing_from": person.missing_from,
                            "date_time": current_time,
                            "location": f"Latitude: {current_latitude}, Longitude: {current_longitude}"
                        }

                        # Capture a short 3-second video
                        video_file_path = capture_video()

                        # Send email with video attachment
                        send_email_with_video(subject, context, recipient_email, video_file_path, is_case_registered=False)

                        # Flag to prevent sending multiple notifications
                        face_detected = True
                        break  # Exit the loop after a match is found

        # Display the resulting image
        cv2.imshow('Camera Feed', frame)

        # Press 'q' to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video_capture.release()
    cv2.destroyAllWindows()
    return render(request, "surveillance.html")


def surveillance(request):
    return render(request, "surveillance.html")


def register(request):
    if request.method == 'POST':
        # Collect form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        father_name = request.POST.get('fathers_name')
        date_of_birth = request.POST.get('dob')
        address = request.POST.get('address')
        phone_number = request.POST.get('phonenum')
        aadhar_number = request.POST.get('aadhar_number')
        missing_from = request.POST.get('missing_date')
        email = request.POST.get('email')
        image = request.FILES.get('image')
        gender = request.POST.get('gender')

        if MissingPerson.objects.filter(aadhar_number=aadhar_number).exists():
            messages.info(request, 'Aadhar Number already exists')
            return redirect('/register')

        # Create MissingPerson record
        person = MissingPerson.objects.create(
            first_name=first_name,
            last_name=last_name,
            father_name=father_name,
            date_of_birth=date_of_birth,
            address=address,
            phone_number=phone_number,
            aadhar_number=aadhar_number,
            missing_from=missing_from,
            email=email,
            image=image,
            gender=gender,
        )
        person.save()
        messages.success(request, 'Case Registered Successfully')

        # Prepare email content
        current_time = datetime.now().strftime('%d-%m-%Y %H:%M')
        subject = 'Case Registered Successfully'
        recipient_email = person.email
        context = {
            "first_name": person.first_name,
            "last_name": person.last_name,
            "fathers_name": person.father_name,
            "aadhar_number": person.aadhar_number,
            "missing_from": person.missing_from,
            "date_time": current_time
        }

        # Send email without video
        send_email_with_video(subject, context, recipient_email, None, is_case_registered=True)

    return render(request, "register.html")


def missing(request):
    queryset = MissingPerson.objects.all()
    search_query = request.GET.get('search', '')
    if search_query:
        queryset = queryset.filter(aadhar_number__icontains=search_query)

    context = {'missingperson': queryset}
    return render(request, "missing.html", context)


def delete_person(request, person_id):
    person = get_object_or_404(MissingPerson, id=person_id)
    person.delete()
    return redirect('missing')  # Redirect to the missing view after deleting


def update_person(request, person_id):
    person = get_object_or_404(MissingPerson, id=person_id)

    if request.method == 'POST':
        # Retrieve form data
        first_name = request.POST.get('first_name', person.first_name)
        last_name = request.POST.get('last_name', person.last_name)
        fathers_name = request.POST.get('fathers_name', person.fathers_name)
        dob = request.POST.get('dob', person.dob)
        address = request.POST.get('address', person.address)
        email = request.POST.get('email', person.email)
        phonenum = request.POST.get('phonenum', person.phonenum)
        aadhar_number = request.POST.get('aadhar_number', person.aadhar_number)
        missing_date = request.POST.get('missing_date', person.missing_date)
        gender = request.POST.get('gender', person.gender)

        # Check if a new image is provided
        new_image = request.FILES.get('image')
        if new_image:
            person.image = new_image

        # Update and save the changes
        person.first_name = first_name
        person.last_name = last_name
        person.fathers_name = fathers_name
        person.dob = dob
        person.address = address
        person.email = email
        person.phonenum = phonenum
        person.aadhar_number = aadhar_number
        person.missing_date = missing_date
        person.gender = gender
        person.save()

        return redirect('missing')  # Redirect to the missing view after editing

    return render(request, 'edit.html', {'person': person})