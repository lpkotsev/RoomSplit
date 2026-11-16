const categoryInput = document.getElementById("category");
const categoryList = document.getElementById("category-suggestions");

if (categoryInput && categoryList) {
  const categories = Array.from(categoryList.options, option => option.value);
  categoryInput.addEventListener("input", () => {
    const prefix = categoryInput.value.trimStart().toLocaleLowerCase();
    const matches = categories.filter(name => name.toLocaleLowerCase().startsWith(prefix));
    categoryList.replaceChildren(...matches.map(name => new Option(name, name)));
  });
}
