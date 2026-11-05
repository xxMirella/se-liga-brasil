// Progressive enhancement of the Step 4 review: turns each native question into clickable
// alternatives with feedback. Without this script the questions stay as <details>.
(function () {
  "use strict";
  var STORAGE_KEY = "seliga-civic-review";

  function loadAnswers() {
    try {
      var saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
      return saved && typeof saved === "object" ? saved : {};
    } catch (error) {
      return {};
    }
  }

  function saveAnswers(answers) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(answers));
    } catch (error) {
      /* storage is optional */
    }
  }

  function readQuestion(details) {
    var labels = (details.getAttribute("data-options") || "").split("|");
    var correctIndex = Number(details.getAttribute("data-correct-index"));
    var answer = details.querySelector(".ds-civic-answer");
    var explanation = answer ? answer.textContent.replace(/^[^.]*\.\s*/, "") : "";
    var summary = details.querySelector("summary");
    return {
      text: summary ? summary.textContent : "",
      options: labels.map(function (label, index) { return { label: label, correct: index === correctIndex }; }),
      explanation: explanation
    };
  }

  function buildCheck(question, index, onPick) {
    var box = document.createElement("div");
    box.className = "ds-civic-check";
    box.setAttribute("role", "group");
    var title = document.createElement("p");
    title.className = "ds-civic-check__question";
    title.id = "civic-question-" + index;
    title.textContent = question.text;
    box.setAttribute("aria-labelledby", title.id);
    var row = document.createElement("div");
    row.className = "ds-civic-check__choices";
    var feedback = document.createElement("p");
    feedback.className = "ds-civic-feedback";
    feedback.setAttribute("role", "status");
    var buttons = question.options.map(function (option, position) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "ds-civic-choice";
      button.textContent = option.label;
      button.setAttribute("aria-pressed", "false");
      button.setAttribute("data-correct", String(option.correct));
      button.addEventListener("click", function () { onPick(position); });
      row.appendChild(button);
      return button;
    });
    box.appendChild(title);
    box.appendChild(row);
    box.appendChild(feedback);
    return { box: box, buttons: buttons, feedback: feedback };
  }

  function showAnswer(check, question, picked) {
    check.buttons.forEach(function (button, position) {
      button.setAttribute("aria-pressed", String(position === picked));
    });
    if (picked === null) {
      check.feedback.textContent = "";
      check.feedback.removeAttribute("data-correct");
      return;
    }
    var right = question.options[picked].correct;
    check.feedback.setAttribute("data-correct", String(right));
    check.feedback.textContent = "";
    var lead = document.createElement("strong");
    lead.textContent = right ? "Isso." : "Ainda não.";
    check.feedback.appendChild(lead);
    check.feedback.appendChild(document.createTextNode(" " + question.explanation));
  }

  function summaryText(answers, questions, baseText) {
    var answered = 0;
    var hits = 0;
    questions.forEach(function (question, index) {
      var picked = answers[index];
      if (typeof picked !== "number" || !question.options[picked]) { return; }
      answered += 1;
      if (question.options[picked].correct) { hits += 1; }
    });
    if (answered === 0) { return baseText; }
    return "Você respondeu " + answered + " de " + questions.length + " checagens e acertou "
      + hits + ". Pense na resposta antes de abrir cada pergunta.";
  }

  function enhance(section) {
    var nodes = Array.prototype.slice.call(section.querySelectorAll("[data-civic-question]"));
    if (!nodes.length) { return; }
    var lead = section.querySelector("[data-civic-lead]");
    var baseText = lead ? lead.textContent : "";
    var reset = section.querySelector("[data-civic-reset]");
    var questions = nodes.map(readQuestion);
    var answers = loadAnswers();
    var checks = [];

    function refresh() {
      checks.forEach(function (check, index) {
        var picked = typeof answers[index] === "number" && questions[index].options[answers[index]] ? answers[index] : null;
        showAnswer(check, questions[index], picked);
      });
      if (lead) { lead.textContent = summaryText(answers, questions, baseText); }
    }

    nodes.forEach(function (details, index) {
      var check = buildCheck(questions[index], index, function (position) {
        answers[index] = position;
        saveAnswers(answers);
        refresh();
      });
      checks.push(check);
      details.replaceWith(check.box);
    });
    if (reset) {
      reset.hidden = false;
      reset.addEventListener("click", function () {
        answers = {};
        saveAnswers(answers);
        refresh();
        if (checks[0]) { checks[0].buttons[0].focus(); }
      });
    }
    refresh();
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-civic-review]"), enhance);
})();
