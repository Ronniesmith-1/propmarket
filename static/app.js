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


// Advertiser photo manager
document.addEventListener("DOMContentLoaded", () => {
    const grid = document.getElementById("photo-manager-grid");
    const input = document.getElementById("photos");
    const addCard = document.getElementById("photo-add-card");
    const orderInput = document.getElementById("photo_order");
    const deletedInput = document.getElementById("deleted_photo_ids");
    const newIdsInput = document.getElementById("new_photo_ids");
    const countBadge = document.getElementById("photo-count-badge");

    if (
        !grid ||
        !input ||
        !addCard ||
        !orderInput ||
        !deletedInput ||
        !newIdsInput
    ) {
        return;
    }

    let selectedFiles = [];
    let deletedExistingIds = [];
    let draggedCard = null;
    let counter = 1;

    function cards() {
        return Array.from(
            grid.querySelectorAll(".photo-manager-card")
        );
    }

    function makeNewId() {
        const value =
            `${Date.now()}-${counter}-${Math.random()
                .toString(36)
                .slice(2, 7)}`;

        counter += 1;
        return value;
    }

    function rebuildInput() {
        const transfer = new DataTransfer();

        selectedFiles.forEach((item) => {
            transfer.items.add(item.file);
        });

        input.files = transfer.files;

        newIdsInput.value = selectedFiles
            .map((item) => item.id)
            .join(",");
    }

    function updateState() {
        const currentCards = cards();

        orderInput.value = currentCards
            .map((card) => card.dataset.photoToken)
            .join(",");

        deletedInput.value =
            deletedExistingIds.join(",");

        currentCards.forEach((card, index) => {
            card.classList.toggle(
                "is-main-photo",
                index === 0
            );
        });

        if (countBadge) {
            const total = currentCards.length;

            countBadge.textContent =
                `${total} photo${total === 1 ? "" : "s"}`;
        }
    }

    function removeCard(card) {
        const existingId =
            card.dataset.existingId;

        const newId =
            card.dataset.newId;

        if (existingId) {
            deletedExistingIds.push(
                existingId
            );
        }

        if (newId) {
            selectedFiles =
                selectedFiles.filter(
                    (item) =>
                        item.id !== newId
                );

            rebuildInput();
        }

        card.remove();
        updateState();
    }

    function bindCard(card) {
        const removeButton =
            card.querySelector(
                ".photo-remove-button"
            );

        if (removeButton) {
            removeButton.addEventListener(
                "click",
                () => removeCard(card)
            );
        }

        card.addEventListener(
            "dragstart",
            () => {
                draggedCard = card;
                card.classList.add(
                    "is-dragging"
                );
            }
        );

        card.addEventListener(
            "dragend",
            () => {
                card.classList.remove(
                    "is-dragging"
                );

                draggedCard = null;
                updateState();
            }
        );
    }

    cards().forEach(bindCard);

    input.addEventListener(
        "change",
        () => {
            const chosenFiles =
                Array.from(input.files);

            chosenFiles.forEach((file) => {
                const duplicate =
                    selectedFiles.some(
                        (item) =>
                            item.file.name === file.name &&
                            item.file.size === file.size &&
                            item.file.lastModified === file.lastModified
                    );

                if (duplicate) {
                    return;
                }

                const id = makeNewId();

                selectedFiles.push({
                    id,
                    file
                });

                const card =
                    document.createElement(
                        "div"
                    );

                card.className =
                    "photo-manager-card new-photo";

                card.draggable = true;

                card.dataset.photoToken =
                    `new:${id}`;

                card.dataset.newId = id;

                card.innerHTML = `
                    <div class="photo-main-badge">
                        Main photo
                    </div>

                    <img alt="New property photo">

                    <div class="photo-card-footer">

                        <span class="drag-handle">
                            ↕ Drag
                        </span>

                        <button type="button"
                                class="photo-remove-button">
                            Remove
                        </button>

                    </div>
                `;

                grid.insertBefore(
                    card,
                    addCard
                );

                const image =
                    card.querySelector("img");

                const reader =
                    new FileReader();

                reader.onload =
                    (event) => {
                        image.src =
                            event.target.result;
                    };

                reader.readAsDataURL(file);

                bindCard(card);
            });

            rebuildInput();
            updateState();
        }
    );

    grid.addEventListener(
        "dragover",
        (event) => {
            event.preventDefault();

            if (!draggedCard) {
                return;
            }

            const target =
                event.target.closest(
                    ".photo-manager-card"
                );

            if (
                target &&
                target !== draggedCard
            ) {
                const box =
                    target.getBoundingClientRect();

                const before =
                    event.clientX <
                    box.left + box.width / 2;

                grid.insertBefore(
                    draggedCard,
                    before
                        ? target
                        : target.nextSibling
                );

                if (
                    addCard.previousSibling !==
                        draggedCard &&
                    draggedCard.nextSibling === null
                ) {
                    grid.insertBefore(
                        draggedCard,
                        addCard
                    );
                }
            }
        }
    );

    updateState();
});
