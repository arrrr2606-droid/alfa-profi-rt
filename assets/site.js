(function () {
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  var filterBar = document.querySelector("[data-filters]");
  if (filterBar) {
    var buttons = filterBar.querySelectorAll("button");
    var cards = document.querySelectorAll("[data-category]");
    var apply = function (slug) {
      buttons.forEach(function (button) {
        button.classList.toggle("is-on", button.getAttribute("data-filter") === slug);
      });
      cards.forEach(function (card) {
        card.hidden = slug !== "all" && card.getAttribute("data-category") !== slug;
      });
    };
    filterBar.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button) return;
      var slug = button.getAttribute("data-filter");
      history.replaceState(null, "", slug === "all" ? location.pathname : "#" + slug);
      apply(slug);
    });
    var initial = (location.hash || "").replace("#", "");
    var known = false;
    buttons.forEach(function (button) {
      if (button.getAttribute("data-filter") === initial) known = true;
    });
    apply(known ? initial : "all");
  }

  document.querySelectorAll("[data-lead]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var error = form.querySelector(".form-error");
      var data = new FormData(form);
      var name = String(data.get("name") || "").trim();
      var phone = String(data.get("phone") || "").trim();
      var model = String(data.get("model") || "").trim();
      var place = String(data.get("place") || "").trim();
      var comment = String(data.get("comment") || "").trim();
      var digits = phone.replace(/\D/g, "");
      var agreed = form.querySelector("[name=pdn]").checked;
      if (name.length < 2 || digits.length < 10) {
        error.hidden = false;
        error.textContent = "Напишите имя и телефон, по которому можно перезвонить.";
        return;
      }
      if (!agreed) {
        error.hidden = false;
        error.textContent = "Поставьте согласие на обработку персональных данных. Без него заявку отправить нельзя.";
        return;
      }
      error.hidden = true;
      var lines = [
        "Заявка с сайта Альфа Машинери, Республика Татарстан.",
        "Согласие на обработку персональных данных: да, " + new Date().toLocaleString("ru-RU"),
        "Имя: " + name,
        "Телефон: " + phone,
        "Техника: " + (model || "нужна помощь с выбором"),
      ];
      if (place) lines.push("Объект: " + place);
      if (comment) lines.push("Комментарий: " + comment);
      var text = lines.join("\n");
      var success = form.parentElement.querySelector(".success");
      success.hidden = false;
      success.querySelector("textarea").value = text;
      var mail = success.querySelector("[data-mail]");
      var wa = success.querySelector("[data-wa]");
      mail.href = "mailto:alfa-mash@bk.ru?subject=" + encodeURIComponent("Заявка на технику Профессионал") + "&body=" + encodeURIComponent(text);
      wa.href = "https://wa.me/79177562606?text=" + encodeURIComponent(text);
      form.hidden = true;
    });
  });

  var hero = document.querySelector("[data-hero]");
  if (hero) {
    var slides = hero.querySelectorAll(".hero-slide");
    var scenes = [
      {
        title: "PB50",
        sub: "Фронтальный погрузчик, 5 тонн",
        stats: [
          ["Мощность", "220 л.с."],
          ["Грузоподъёмность", "5 000 кг"],
          ["Скорость", "36 км/ч"]
        ]
      },
      {
        title: "PB 991",
        sub: "Экскаватор-погрузчик",
        stats: [
          ["Мощность", "99,3 л.с."],
          ["Грузоподъёмность", "3 900 кг"],
          ["Скорость", "40 км/ч"]
        ]
      }
    ];
    var index = 0;
    var title = hero.querySelector("[data-hero-title]");
    var sub = hero.querySelector("[data-hero-sub]");
    var labels = hero.querySelectorAll("[data-stat-label]");
    var values = hero.querySelectorAll("[data-stat-value]");
    var count = hero.querySelector("[data-hero-count]");
    var show = function (next) {
      index = (next + slides.length) % slides.length;
      slides.forEach(function (slide, slideIndex) {
        slide.classList.toggle("is-on", slideIndex === index);
      });
      var scene = scenes[index];
      title.textContent = scene.title;
      sub.textContent = scene.sub;
      scene.stats.forEach(function (pair, pairIndex) {
        labels[pairIndex].textContent = pair[0];
        values[pairIndex].textContent = pair[1];
      });
      count.textContent = "0" + (index + 1);
    };
    hero.querySelector("[data-hero-prev]").addEventListener("click", function () { show(index - 1); });
    hero.querySelector("[data-hero-next]").addEventListener("click", function () { show(index + 1); });
  }

  var lease = document.querySelector("[data-lease]");
  if (lease) {
    var price = lease.querySelector("[name=price]");
    var advance = lease.querySelector("[name=advance]");
    var term = lease.querySelector("[name=term]");
    var payment = lease.querySelector("[data-payment]");
    var advanceLabel = lease.querySelector("[data-advance]");
    var termLabel = lease.querySelector("[data-term]");
    var render = function () {
      var cost = Number(price.value) || 0;
      var advancePct = Number(advance.value) || 0;
      var months = Number(term.value) || 12;
      var financed = cost * (1 - advancePct / 100);
      var total = financed * (1 + 0.1 * (months / 12));
      var monthly = Math.round(total / months);
      payment.textContent = monthly.toLocaleString("ru-RU") + " ₽/мес.";
      advanceLabel.textContent = advancePct + "%";
      termLabel.textContent = months + " мес.";
    };
    lease.addEventListener("submit", function (event) { event.preventDefault(); });
    lease.addEventListener("input", render);
    render();
  }

  var cookieBar = document.querySelector("[data-cookie]");
  var consentKey = "alfa-consent";
  var readConsent = function () {
    try {
      return JSON.parse(window.localStorage.getItem(consentKey) || "null");
    } catch (error) {
      return null;
    }
  };
  var writeConsent = function (analytics, ads) {
    var choice = {
      necessary: true,
      analytics: !!analytics,
      ads: !!ads,
      at: new Date().toISOString()
    };
    window.localStorage.setItem(consentKey, JSON.stringify(choice));
    if (cookieBar) cookieBar.hidden = true;
    if (typeof window.alfaLoadCounters === "function") window.alfaLoadCounters(choice);
    return choice;
  };
  window.alfaLoadCounters = function (choice) {
    if (!choice || (!choice.analytics && !choice.ads) || window.__alfaCountersLoaded) return;
    window.__alfaCountersLoaded = true;
  };
  if (cookieBar) {
    var analyticsBox = cookieBar.querySelector("[data-consent=analytics]");
    var adsBox = cookieBar.querySelector("[data-consent=ads]");
    var openCookie = function () {
      var saved = readConsent();
      analyticsBox.checked = !!(saved && saved.analytics);
      adsBox.checked = !!(saved && saved.ads);
      cookieBar.hidden = false;
    };
    cookieBar.querySelector("[data-cookie-reject]").addEventListener("click", function () {
      analyticsBox.checked = false;
      adsBox.checked = false;
      writeConsent(false, false);
    });
    cookieBar.querySelector("[data-cookie-save]").addEventListener("click", function () {
      writeConsent(analyticsBox.checked, adsBox.checked);
    });
    document.querySelectorAll("[data-cookie-open]").forEach(function (button) {
      button.addEventListener("click", openCookie);
    });
    if (!readConsent()) openCookie();
    else window.alfaLoadCounters(readConsent());
  }
})();
