document.addEventListener("DOMContentLoaded", () => {
    const photos = document.getElementById("photos");
    const fileCount = document.getElementById("file-count");

    if (photos && fileCount) {
        photos.addEventListener("change", () => {
            if (photos.files.length) {
                fileCount.textContent = `${photos.files.length} file(s) selected`;
            } else {
                fileCount.textContent = "No files selected";
            }
        });
    }

    document.querySelectorAll(".flash").forEach((flash) => {
        setTimeout(() => {
            flash.style.opacity = "0";

            setTimeout(() => {
                flash.remove();
            }, 400);
        }, 4500);
    });
});
