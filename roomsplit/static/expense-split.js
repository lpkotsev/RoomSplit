const splitType = document.getElementById("split-type");
const customShares = document.querySelectorAll(".custom-share");

function updateCustomShares() {
  customShares.forEach((share) => {
    share.hidden = splitType.value !== "custom";
  });
}

splitType.addEventListener("change", updateCustomShares);
updateCustomShares();
