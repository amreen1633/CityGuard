const reportForm = document.getElementById("reportForm");

const imageInput = document.getElementById("image");

const imagePreview =
    document.getElementById("imagePreview");

const imagePreviewContainer =
    document.getElementById("imagePreviewContainer");

const message =
    document.getElementById("message");


/* Show selected image */

imageInput.addEventListener("change", function () {

    const file = imageInput.files[0];

    if (!file) {

        imagePreviewContainer.style.display = "none";

        return;
    }

    const imageURL =
        URL.createObjectURL(file);

    imagePreview.src = imageURL;

    imagePreviewContainer.style.display = "block";

});


/* Submit report */

reportForm.addEventListener("submit", function (event) {

    event.preventDefault();


    const title =
        document.getElementById("title").value;

    const description =
        document.getElementById("description").value;

    const location =
        document.getElementById("location").value;

    const severity =
        document.getElementById("severity").value;


    console.log("CityGuard Report:");

    console.log({
        title,
        description,
        location,
        severity
    });


    message.textContent =
        "✅ Report submitted successfully!";

    message.style.display =
        "block";


    reportForm.reset();

    imagePreviewContainer.style.display =
        "none";

});