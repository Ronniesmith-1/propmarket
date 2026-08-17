document.addEventListener("DOMContentLoaded", () => {
  const photos = document.getElementById("photos");
  const count = document.getElementById("file-count");

  if (photos && count) {
    photos.addEventListener("change", () => {
      count.textContent = photos.files.length
        ? `${photos.files.length} file(s) selected`
        : "No files selected";
    });
  }

  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => {
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 400);
    }, 4500);
  });
});
