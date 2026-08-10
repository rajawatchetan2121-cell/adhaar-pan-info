import re
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Document Verification",
    page_icon="🪪",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# DATABASE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "documents.db"


def get_connection():
    """
    Create a connection to the SQLite database.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """
    Create the documents table if it does not already exist.
    """
    conn = get_connection()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_type TEXT NOT NULL,
            name TEXT NOT NULL,
            dob TEXT,
            gender TEXT,
            father_name TEXT,
            id_number TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def save_record(
    doc_type,
    name,
    dob,
    gender,
    father_name,
    id_number,
):
    """
    Save a human-verified document record.
    """
    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO documents
        (
            doc_type,
            name,
            dob,
            gender,
            father_name,
            id_number,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_type,
            name,
            dob,
            gender,
            father_name,
            id_number,
            datetime.utcnow().isoformat(),
        ),
    )

    conn.commit()
    record_id = cursor.lastrowid
    conn.close()

    return record_id


def get_records(search_term=""):
    """
    Get saved records.
    Search by name or ID number.
    """
    conn = get_connection()

    if search_term:
        search = f"%{search_term}%"

        rows = conn.execute(
            """
            SELECT *
            FROM documents
            WHERE name LIKE ?
               OR id_number LIKE ?
            ORDER BY created_at DESC
            """,
            (search, search),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM documents
            ORDER BY created_at DESC
            """
        ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def delete_record(record_id):
    """
    Delete a saved record.
    """
    conn = get_connection()

    conn.execute(
        "DELETE FROM documents WHERE id = ?",
        (record_id,),
    )

    conn.commit()
    conn.close()


# Initialize database
init_database()


# ============================================================
# OCR / IMAGE FUNCTIONS
# ============================================================

def prepare_image(image):
    """
    Basic image preparation before OCR.

    Converts image to grayscale, improves contrast,
    sharpens the image and returns the processed image.
    """
    image = image.convert("RGB")

    gray = image.convert("L")

    contrast = ImageEnhance.Contrast(gray)
    gray = contrast.enhance(1.5)

    sharp = ImageEnhance.Sharpness(gray)
    gray = sharp.enhance(1.5)

    gray = gray.filter(ImageFilter.SHARPEN)

    return gray


def run_ocr(image):
    """
    Run Tesseract OCR.

    The original project used Tesseract.js with English OCR,
    so this version also uses English OCR.
    """
    processed_image = prepare_image(image)

    text = pytesseract.image_to_string(
        processed_image,
        lang="eng",
        config="--psm 6",
    )

    return text


# ============================================================
# DOCUMENT CLASSIFICATION
# ============================================================

def classify_document(text):
    """
    Decide whether OCR text looks like Aadhaar or PAN.

    Similar logic to the original JavaScript classifyDocument()
    function.
    """

    if not text:
        return "none"

    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", text)

    # Aadhaar pattern
    has_aadhaar_number = bool(
        re.search(
            r"\b\d{4}\s?\d{4}\s?\d{4}\b",
            normalized,
        )
    )

    # PAN pattern
    has_pan_number = bool(
        re.search(
            r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
            normalized.upper(),
        )
    )

    # Aadhaar-specific words
    aadhaar_markers = bool(
        re.search(
            r"(aadhaar|आधार|uidai|unique identification authority|government of india)",
            normalized,
            re.IGNORECASE,
        )
    )

    # PAN-specific words
    pan_markers = bool(
        re.search(
            r"(income\s*tax|permanent account number|govt\.?\s*of india|इनकम टैक्स)",
            normalized,
            re.IGNORECASE,
        )
    )

    looks_like_aadhaar = (
        has_aadhaar_number and aadhaar_markers
    )

    looks_like_pan = (
        has_pan_number and pan_markers
    )

    if looks_like_aadhaar and not looks_like_pan:
        return "aadhaar"

    if looks_like_pan and not looks_like_aadhaar:
        return "pan"

    if looks_like_aadhaar and looks_like_pan:
        return "ambiguous"

    # Fallback:
    # If a clear ID pattern exists, return that type.
    if has_aadhaar_number and not has_pan_number:
        return "aadhaar"

    if has_pan_number and not has_aadhaar_number:
        return "pan"

    return "none"


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_lines(text):
    """
    Split OCR text into clean non-empty lines.
    """
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


def normalize_spaces(value):
    """
    Remove duplicate spaces.
    """
    return re.sub(r"\s+", " ", value).strip()


def find_date(text):
    """
    Find DD/MM/YYYY style date.
    """
    match = re.search(
        r"\b(\d{2}[\/\-.]\d{2}[\/\-.]\d{4})\b",
        text,
    )

    if not match:
        return ""

    return (
        match.group(1)
        .replace("-", "/")
        .replace(".", "/")
    )


def find_aadhaar_number(text):
    """
    Find Aadhaar number.
    """
    match = re.search(
        r"\b\d{4}\s?\d{4}\s?\d{4}\b",
        text,
    )

    if not match:
        return ""

    return re.sub(
        r"\s+",
        " ",
        match.group(0).strip(),
    )


def find_pan_number(text):
    """
    Find PAN number.
    """
    match = re.search(
        r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
        text.upper(),
    )

    if not match:
        return ""

    return match.group(0)


def looks_like_person_name(line):
    """
    Heuristic for detecting a person's name from OCR lines.
    """

    line = normalize_spaces(line)

    if not line:
        return False

    # Don't use lines containing digits
    if re.search(r"\d", line):
        return False

    # Remove punctuation for analysis
    letters_only = re.sub(
        r"[^A-Za-z ]",
        "",
        line,
    ).strip()

    if len(letters_only) < 4:
        return False

    # Most characters should be alphabetic
    alpha_count = len(
        re.findall(r"[A-Za-z]", line)
    )

    if len(line) == 0:
        return False

    alpha_ratio = alpha_count / len(line)

    if alpha_ratio < 0.80:
        return False

    return True


# ============================================================
# AADHAAR PARSER
# ============================================================

def parse_aadhaar(text):
    """
    Extract Aadhaar fields from OCR text.

    Fields:
    - name
    - dob
    - gender
    - father_name
    - id_number
    - flags
    """

    lines = clean_lines(text)

    result = {
        "name": "",
        "dob": "",
        "gender": "",
        "father_name": "",
        "id_number": "",
        "flags": {},
    }

    # --------------------------------------------------------
    # Aadhaar number
    # --------------------------------------------------------

    result["id_number"] = find_aadhaar_number(text)

    if not result["id_number"]:
        result["flags"]["id_number"] = True

    # --------------------------------------------------------
    # DOB
    # --------------------------------------------------------

    result["dob"] = find_date(text)

    # If DOB is not available, look for year of birth
    if not result["dob"]:

        yob_match = re.search(
            r"(?:year\s*of\s*birth|yob)[^\d]{0,10}(\d{4})",
            text,
            re.IGNORECASE,
        )

        if yob_match:
            result["dob"] = yob_match.group(1)

    if not result["dob"]:
        result["flags"]["dob"] = True

    # --------------------------------------------------------
    # Gender
    # --------------------------------------------------------

    if re.search(r"\bFEMALE\b", text, re.IGNORECASE):
        result["gender"] = "Female"

    elif re.search(r"\bMALE\b", text, re.IGNORECASE):
        result["gender"] = "Male"

    else:
        result["flags"]["gender"] = True

    # --------------------------------------------------------
    # Name
    # --------------------------------------------------------

    stopwords = re.compile(
        r"""
        government|
        india|
        male|
        female|
        dob|
        date\s*of\s*birth|
        birth|
        aadhaar|
        uidai|
        address|
        unique|
        identification|
        authority|
        download|
        year\s*of\s*birth|
        enrolment|
        enrollment
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    for line in lines:

        line = normalize_spaces(line)

        if stopwords.search(line):
            continue

        if re.search(r"\d", line):
            continue

        if looks_like_person_name(line):

            name = re.sub(
                r"[^A-Za-z .]",
                "",
                line,
            ).strip()

            if name:
                result["name"] = name
                break

    if not result["name"]:
        result["flags"]["name"] = True

    # --------------------------------------------------------
    # Father's name
    # --------------------------------------------------------
    #
    # As in your original project, leave this for manual
    # verification because it may not be reliably available.
    #

    result["father_name"] = ""
    result["flags"]["father"] = True

    return result


# ============================================================
# PAN PARSER
# ============================================================

def parse_pan(text):
    """
    Extract PAN fields from OCR text.
    """

    lines = clean_lines(text)

    result = {
        "name": "",
        "dob": "",
        "gender": "",
        "father_name": "",
        "id_number": "",
        "flags": {},
    }

    # --------------------------------------------------------
    # PAN number
    # --------------------------------------------------------

    result["id_number"] = find_pan_number(text)

    if not result["id_number"]:
        result["flags"]["id_number"] = True

    # --------------------------------------------------------
    # DOB
    # --------------------------------------------------------

    result["dob"] = find_date(text)

    if not result["dob"]:
        result["flags"]["dob"] = True

    # --------------------------------------------------------
    # Name / Father's name
    # --------------------------------------------------------

    stopwords = re.compile(
        r"""
        income\s*tax|
        govt|
        government|
        india|
        permanent\s*account|
        department|
        signature|
        date\s*of\s*birth|
        father|
        father's|
        father’s|
        account\s*number
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    candidates = []

    for line in lines:

        line = normalize_spaces(line)

        if stopwords.search(line):
            continue

        if re.search(r"\d", line):
            continue

        if looks_like_person_name(line):

            cleaned = re.sub(
                r"[^A-Za-z .]",
                "",
                line,
            ).strip()

            if cleaned:
                candidates.append(cleaned)

    # First candidate = name
    if len(candidates) >= 1:
        result["name"] = candidates[0]
    else:
        result["flags"]["name"] = True

    # Second candidate = father's name
    if len(candidates) >= 2:
        result["father_name"] = candidates[1]
    else:
        result["flags"]["father"] = True

    # PAN cards do not provide gender in the same way as Aadhaar
    result["gender"] = ""

    return result


# ============================================================
# SESSION STATE
# ============================================================

def initialize_session_state():

    defaults = {
        "doc_type": "Aadhaar",
        "uploaded_image": None,
        "ocr_text": "",
        "extracted": None,
        "verification_ready": False,
        "last_saved": False,
    }

    for key, value in defaults.items():

        if key not in st.session_state:
            st.session_state[key] = value


initialize_session_state()


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }

    .subtitle {
        color: #667085;
        margin-bottom: 1.5rem;
    }

    .section-title {
        font-size: 1.4rem;
        font-weight: 650;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }

    .success-box {
        padding: 1rem;
        border-radius: 10px;
        background: #ecfdf3;
        border: 1px solid #a6f4c5;
        color: #027a48;
        margin: 1rem 0;
    }

    .warning-box {
        padding: 1rem;
        border-radius: 10px;
        background: #fffaeb;
        border: 1px solid #fedf89;
        color: #b54708;
        margin: 1rem 0;
    }

    .danger-box {
        padding: 1rem;
        border-radius: 10px;
        background: #fef3f2;
        border: 1px solid #fecdca;
        color: #b42318;
        margin: 1rem 0;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

st.sidebar.title("🪪 Document Verification")

st.sidebar.caption(
    "Aadhaar & PAN extraction module"
)

page = st.sidebar.radio(
    "Navigation",
    [
        "Extract Document",
        "Dashboard",
    ],
)


# ============================================================
# EXTRACT DOCUMENT PAGE
# ============================================================

if page == "Extract Document":

    st.markdown(
        '<div class="main-title">Extract from ID document</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="subtitle">'
        'Upload a clear Aadhaar or PAN image. '
        'The application will read the document and allow '
        'you to verify the extracted information before saving.'
        '</div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Document type
    # --------------------------------------------------------

    doc_type = st.radio(
        "Document type",
        [
            "Aadhaar",
            "PAN",
        ],
        horizontal=True,
        index=0 if st.session_state.doc_type == "Aadhaar" else 1,
    )

    st.session_state.doc_type = doc_type

    st.divider()

    # --------------------------------------------------------
    # Upload
    # --------------------------------------------------------

    uploaded_file = st.file_uploader(
        "Upload document image",
        type=[
            "jpg",
            "jpeg",
            "png",
        ],
        help=(
            "Upload a clear, well-lit and uncropped "
            "front-side image of the document."
        ),
    )

    if uploaded_file is not None:

        try:

            image = Image.open(uploaded_file)

            st.session_state.uploaded_image = image

            st.image(
                image,
                caption=uploaded_file.name,
                width="stretch",
            )

            st.success(
                "Image uploaded successfully."
            )

        except Exception as error:

            st.error(
                f"Could not open the image: {error}"
            )

    # --------------------------------------------------------
    # Extract button
    # --------------------------------------------------------

    if st.session_state.uploaded_image is not None:

        extract_clicked = st.button(
            "🔍 Extract Details",
            type="primary",
            use_container_width=True,
        )

        if extract_clicked:

            with st.spinner(
                "Reading document with OCR..."
            ):

                try:

                    # Run OCR
                    ocr_text = run_ocr(
                        st.session_state.uploaded_image
                    )

                    st.session_state.ocr_text = ocr_text

                    if not ocr_text.strip():

                        st.error(
                            "No readable text was found. "
                            "Please upload a clearer image."
                        )

                        st.session_state.extracted = None
                        st.session_state.verification_ready = False

                    else:

                        # Classify document
                        detected = classify_document(
                            ocr_text
                        )

                        expected = (
                            "aadhaar"
                            if doc_type == "Aadhaar"
                            else "pan"
                        )

                        # ------------------------------------------------
                        # No document detected
                        # ------------------------------------------------

                        if detected == "none":

                            st.error(
                                "No Aadhaar or PAN card detected."
                            )

                            st.info(
                                "Please upload a clear image "
                                "of the selected document."
                            )

                            st.session_state.extracted = None
                            st.session_state.verification_ready = False

                        # ------------------------------------------------
                        # Wrong document
                        # ------------------------------------------------

                        elif (
                            detected != expected
                            and detected != "ambiguous"
                        ):

                            detected_label = (
                                "Aadhaar"
                                if detected == "aadhaar"
                                else "PAN"
                            )

                            st.error(
                                f"This image looks like a "
                                f"{detected_label} card, not a "
                                f"{doc_type} card."
                            )

                            st.session_state.extracted = None
                            st.session_state.verification_ready = False

                        # ------------------------------------------------
                        # Correct document
                        # ------------------------------------------------

                        else:

                            if expected == "aadhaar":

                                extracted = parse_aadhaar(
                                    ocr_text
                                )

                            else:

                                extracted = parse_pan(
                                    ocr_text
                                )

                            st.session_state.extracted = extracted
                            st.session_state.verification_ready = True

                            st.success(
                                f"{doc_type} document detected."
                            )

                except Exception as error:

                    st.error(
                        "OCR failed."
                    )

                    st.code(
                        str(error)
                    )

                    st.info(
                        "Make sure Tesseract OCR is installed "
                        "and available to Python."
                    )

    # --------------------------------------------------------
    # OCR result
    # --------------------------------------------------------

    if st.session_state.ocr_text:

        with st.expander(
            "View raw OCR text"
        ):

            st.text(
                st.session_state.ocr_text.strip()
            )


# ============================================================
# VERIFICATION
# ============================================================

if (
    page == "Extract Document"
    and st.session_state.verification_ready
    and st.session_state.extracted is not None
):

    st.divider()

    st.markdown(
        '<div class="section-title">Step 02 · Verify details</div>',
        unsafe_allow_html=True,
    )

    extracted = st.session_state.extracted

    flags = extracted.get(
        "flags",
        {},
    )

    flag_count = len(flags)

    if flag_count == 0:

        st.success(
            "All fields were read. Please still verify them against the image."
        )

    else:

        st.warning(
            f"{flag_count} field(s) need manual verification."
        )

    # --------------------------------------------------------
    # Show original image
    # --------------------------------------------------------

    with st.expander(
        "View uploaded document"
    ):

        if st.session_state.uploaded_image is not None:

            st.image(
                st.session_state.uploaded_image,
                width="stretch",
            )

    # --------------------------------------------------------
    # Verification form
    # --------------------------------------------------------

    with st.form("verification_form"):

        st.subheader(
            f"Verify {st.session_state.doc_type} details"
        )

        name = st.text_input(
            "Full name",
            value=extracted.get(
                "name",
                "",
            ),
        )

        dob = st.text_input(
            "Date of birth",
            value=extracted.get(
                "dob",
                "",
            ),
            placeholder="DD/MM/YYYY",
        )

        # Gender
        if st.session_state.doc_type == "Aadhaar":

            gender_options = [
                "",
                "Male",
                "Female",
            ]

            extracted_gender = extracted.get(
                "gender",
                "",
            )

            gender_index = (
                gender_options.index(extracted_gender)
                if extracted_gender in gender_options
                else 0
            )

            gender = st.selectbox(
                "Gender",
                gender_options,
                index=gender_index,
            )

        else:

            gender = ""

        father_name = st.text_input(
            "Father's name",
            value=extracted.get(
                "father_name",
                "",
            ),
        )

        id_label = (
            "Aadhaar number"
            if st.session_state.doc_type == "Aadhaar"
            else "PAN number"
        )

        id_number = st.text_input(
            id_label,
            value=extracted.get(
                "id_number",
                "",
            ),
        )

        st.caption(
            "Please compare these values with the uploaded document "
            "before saving."
        )

        confirm = st.form_submit_button(
            "✓ Confirm & Save",
            type="primary",
            use_container_width=True,
        )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    if confirm:

        name = name.strip()
        dob = dob.strip()
        father_name = father_name.strip()
        id_number = id_number.strip()

        if not name:

            st.error(
                "Full name is required."
            )

        elif not id_number:

            st.error(
                f"{id_label} is required."
            )

        else:

            try:

                record_id = save_record(
                    doc_type=(
                        "aadhaar"
                        if st.session_state.doc_type == "Aadhaar"
                        else "pan"
                    ),
                    name=name,
                    dob=dob,
                    gender=gender,
                    father_name=father_name,
                    id_number=id_number,
                )

                st.success(
                    f"Record #{record_id} saved successfully."
                )

                # Clear current extraction
                st.session_state.uploaded_image = None
                st.session_state.ocr_text = ""
                st.session_state.extracted = None
                st.session_state.verification_ready = False
                st.session_state.last_saved = True

            except Exception as error:

                st.error(
                    f"Could not save record: {error}"
                )


# ============================================================
# DASHBOARD
# ============================================================

elif page == "Dashboard":

    st.markdown(
        '<div class="main-title">Verified Documents</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="subtitle">'
        'Every record shown here has been human-confirmed before saving.'
        '</div>',
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # Search
    # --------------------------------------------------------

    search_term = st.text_input(
        "Search by name or ID number",
        placeholder="Type a name or number...",
    )

    records = get_records(
        search_term
    )

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    all_records = get_records()

    total_count = len(all_records)

    aadhaar_count = sum(
        1
        for record in all_records
        if record["doc_type"] == "aadhaar"
    )

    pan_count = sum(
        1
        for record in all_records
        if record["doc_type"] == "pan"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Total Verified",
            total_count,
        )

    with col2:

        st.metric(
            "Aadhaar",
            aadhaar_count,
        )

    with col3:

        st.metric(
            "PAN",
            pan_count,
        )

    st.divider()

    # --------------------------------------------------------
    # Records
    # --------------------------------------------------------

    if not records:

        if search_term:

            st.info(
                "No matching records found."
            )

        else:

            st.info(
                "No verified documents have been saved yet."
            )

    else:

        st.subheader(
            f"Records ({len(records)})"
        )

        for record in records:

            record_type = (
                "Aadhaar"
                if record["doc_type"] == "aadhaar"
                else "PAN"
            )

            with st.container(
                border=True
            ):

                col1, col2, col3 = st.columns(
                    [1, 5, 1]
                )

                with col1:

                    if record_type == "Aadhaar":

                        st.markdown(
                            "### 🪪"
                        )

                    else:

                        st.markdown(
                            "### 🧾"
                        )

                with col2:

                    st.markdown(
                        f"**{record['name']}**"
                    )

                    st.caption(
                        f"{record_type} · "
                        f"{record['id_number']}"
                    )

                    if record["dob"]:

                        st.caption(
                            f"DOB: {record['dob']}"
                        )

                    if record["gender"]:

                        st.caption(
                            f"Gender: {record['gender']}"
                        )

                    if record["father_name"]:

                        st.caption(
                            f"Father's name: "
                            f"{record['father_name']}"
                        )

                    created_at = record[
                        "created_at"
                    ]

                    st.caption(
                        f"Saved: {created_at}"
                    )

                with col3:

                    delete_key = (
                        f"delete_{record['id']}"
                    )

                    if st.button(
                        "🗑️",
                        key=delete_key,
                        help="Delete this record",
                    ):

                        delete_record(
                            record["id"]
                        )

                        st.success(
                            "Record deleted."
                        )

                        st.rerun()


# ============================================================
# SIDEBAR INFORMATION
# ============================================================

st.sidebar.divider()

st.sidebar.caption(
    "OCR: Tesseract"
)

st.sidebar.caption(
    "Database: SQLite"
)

st.sidebar.caption(
    "Framework: Streamlit"
)