function expandAct(element) {
    parentElement = element.closest('activity');
    parentElement.classList.toggle('expanded');
}