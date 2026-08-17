document.addEventListener("DOMContentLoaded", () => {
    const photos = document.getElementById("photos");
    const fileCount = document.getElementById("file-count");


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


// Multi-photo uploader: keeps earlier selected photos when the user
// opens the file picker again and chooses additional files.
document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("photos");
    const count = document.getElementById("file-count");
    const preview = document.getElementById("photo-preview-list");

    if (!input || !count) {
        return;
    }

    let selectedFiles = [];

    function rebuildInputFiles() {
        const transfer = new DataTransfer();

        selectedFiles.forEach((file) => {
            transfer.items.add(file);
        });

        input.files = transfer.files;
    }

    function renderSelectedFiles() {
        count.textContent = selectedFiles.length
            ? `${selectedFiles.length} photo(s) selected`
            : "No files selected";

        if (!preview) {
            return;
        }

        preview.innerHTML = "";

        selectedFiles.forEach((file, index) => {
            const item = document.createElement("div");

            item.style.width = "110px";
            item.style.border = "1px solid #e5e7eb";
            item.style.borderRadius = "8px";
            item.style.overflow = "hidden";
            item.style.background = "#fff";

            const img = document.createElement("img");
            img.style.width = "110px";
            img.style.height = "78px";
            img.style.objectFit = "cover";
            img.style.display = "block";

            const reader = new FileReader();

            reader.onload = (event) => {
                img.src = event.target.result;
            };

            reader.readAsDataURL(file);

            const remove = document.createElement("button");
            remove.type = "button";
            remove.textContent = "Remove";
            remove.style.width = "100%";
            remove.style.border = "0";
            remove.style.borderTop = "1px solid #e5e7eb";
            remove.style.padding = "6px";
            remove.style.cursor = "pointer";
            remove.style.background = "#fff";

            remove.addEventListener("click", () => {
                selectedFiles.splice(index, 1);
                rebuildInputFiles();
                renderSelectedFiles();
            });

            item.appendChild(img);
            item.appendChild(remove);
            preview.appendChild(item);
        });
    }

    input.addEventListener("change", () => {
        const newFiles = Array.from(input.files);

        newFiles.forEach((file) => {
            const duplicate = selectedFiles.some(
                (existing) =>
                    existing.name === file.name &&
                    existing.size === file.size &&
                    existing.lastModified === file.lastModified
            );

            if (!duplicate) {
                selectedFiles.push(file);
            }
        });

        rebuildInputFiles();
        renderSelectedFiles();
    });

    renderSelectedFiles();
});
