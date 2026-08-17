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


// Property photo gallery
document.addEventListener("DOMContentLoaded", () => {
    const mainImage = document.getElementById("main-property-image");
    const thumbs = Array.from(document.querySelectorAll(".gallery-thumb"));
    const prevButton = document.getElementById("gallery-prev");
    const nextButton = document.getElementById("gallery-next");
    const counter = document.getElementById("gallery-counter");

    if (!mainImage) {
        return;
    }

    let images = [];

    if (thumbs.length) {
        images = thumbs.map((thumb) => thumb.dataset.image);
        mainImage.src = images[0];
    } else {
        images = [mainImage.src];
    }

    let currentIndex = 0;

    function updateGallery(index) {
        currentIndex = index;

        mainImage.src = images[currentIndex];

        thumbs.forEach((thumb, thumbIndex) => {
            thumb.classList.toggle(
                "active",
                thumbIndex === currentIndex
            );
        });

        if (counter) {
            counter.textContent =
                `${currentIndex + 1} / ${images.length}`;
        }

        const showControls = images.length > 1;

        if (prevButton) {
            prevButton.style.display =
                showControls ? "flex" : "none";
        }

        if (nextButton) {
            nextButton.style.display =
                showControls ? "flex" : "none";
        }

        if (counter) {
            counter.style.display =
                showControls ? "block" : "none";
        }
    }

    thumbs.forEach((thumb, index) => {
        thumb.addEventListener("click", () => {
            updateGallery(index);
        });
    });

    if (prevButton) {
        prevButton.addEventListener("click", () => {
            const nextIndex =
                (currentIndex - 1 + images.length)
                % images.length;

            updateGallery(nextIndex);
        });
    }

    if (nextButton) {
        nextButton.addEventListener("click", () => {
            const nextIndex =
                (currentIndex + 1)
                % images.length;

            updateGallery(nextIndex);
        });
    }

    document.addEventListener("keydown", (event) => {
        if (images.length <= 1) {
            return;
        }

        if (event.key === "ArrowLeft") {
            prevButton?.click();
        }

        if (event.key === "ArrowRight") {
            nextButton?.click();
        }
    });

    updateGallery(0);
});
