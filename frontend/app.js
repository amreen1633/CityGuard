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

    const imageURL = URL.createObjectURL(file);

    imagePreview.src = imageURL;

    imagePreviewContainer.style.display = "block";
});


/* Submit report to CityGuard backend */

reportForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    const title =
        document.getElementById("title").value;

    const description =
        document.getElementById("description").value;

    const location =
        document.getElementById("location").value;

    const severity =
        document.getElementById("severity").value;

    const formData = new FormData();

    formData.append("title", title);
    formData.append("description", description);
    formData.append("location", location);
    formData.append("severity", severity);

    if (imageInput.files[0]) {
        formData.append("image", imageInput.files[0]);
    }

    try {

        const response = await fetch(
            "http://127.0.0.1:8000/reports",
            {
                method: "POST",
                body: formData
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to submit report");
        }

        console.log("CityGuard Report saved:", data);

        message.textContent =
            "✅ Report submitted successfully!";

        message.style.display = "block";

        reportForm.reset();

        imagePreviewContainer.style.display =
            "none";

    } catch (error) {

        console.error("Error:", error);

        message.textContent =
            "❌ Failed to submit report. Please try again.";

        message.style.display =
            "block";
    }

});