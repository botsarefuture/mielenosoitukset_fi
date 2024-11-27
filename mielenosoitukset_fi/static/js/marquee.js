let _current_marg = "";

/**
 * Display a marquee message.
 *
 * Parameters
 * ----------
 * message : str
 *     The message to display in the marquee.
 * style : str
 *     The CSS style to apply to the marquee element.
 * h2_style : str
 *     The CSS style to apply to the h2 element within the marquee.
 */
function displayMarqueeMessage(message, style, h2_style) {
  if (message !== _current_marg) {
    _current_marg = message;
    const marqueeElement = document.querySelector(".marquee");
    marqueeElement.innerHTML = `<h2 style="${h2_style}">${message}</h2>`;
    marqueeElement.style.display = "block"; // Show marquee
    marqueeElement.style = style; // Apply additional styles if any
  } else {
    console.log("The marquee is the same already");
  }
}

/**
 * Check for new marquee messages from the server.
 */
function checkForNewMarqueeMessages() {
  fetch("/marquee")
    .then((response) => response.json())
    .then((data) => {
      const marqueeElement = document.querySelector(".marquee");
      if (data.message !== "NO") {
        displayMarqueeMessage(data.message, data.style, data.h2_style);
      } else {
        marqueeElement.style.display = "none"; // Hide if no message
      }
    })
    .catch((error) => console.error("Error fetching marquee message:", error));
}