(function () {
      var rawPhone = "5515996705738";
      var cleanPhone = rawPhone.replace(/\D/g, "");
      if (cleanPhone.length >= 10 && cleanPhone.length <= 11 && !cleanPhone.startsWith("55")) {
        cleanPhone = "55" + cleanPhone;
      }

      // 1. Links diretos do WhatsApp
      document.querySelectorAll("[data-wa-direct]").forEach(function (link) {
        if (cleanPhone) {
          var defaultMsg = encodeURIComponent("Olá! Gostaria de informações sobre agendamento de consulta na Unic Clínica.");
          link.setAttribute("href", "https://wa.me/" + cleanPhone + "?text=" + defaultMsg);
          link.setAttribute("target", "_blank");
          link.setAttribute("rel", "noopener noreferrer");
        }
      });

      // 2. Sticky header scroll state
      var header = document.getElementById("site-header");
      if (header) {
        var onScroll = function () {
          header.setAttribute("data-scrolled", window.scrollY > 12 ? "true" : "false");
        };
        window.addEventListener("scroll", onScroll, { passive: true });
        onScroll();
      }

      // 3. Sonner-inspired Toast (interruptible CSS transition + pause on hover/tab hidden)
      var toastRegion = document.getElementById("toast-region");
      function showToast(message) {
        if (!toastRegion) return;
        // Limita a 2 toasts visíveis para não poluir
        while (toastRegion.children.length >= 2) {
          toastRegion.removeChild(toastRegion.firstChild);
        }

        var el = document.createElement("div");
        el.className = "craft-toast";
        el.setAttribute("data-state", "entering");
        el.setAttribute("role", "status");
        el.innerHTML =
          '<svg class="w-4 h-4 text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5" aria-hidden="true">' +
          '<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>' +
          '<span></span>';
        el.querySelector("span").textContent = message;
        toastRegion.appendChild(el);

        requestAnimationFrame(function () {
          el.setAttribute("data-state", "open");
        });

        var remaining = 2600;
        var startedAt = Date.now();
        var timer = null;

        function dismiss() {
          clearTimeout(timer);
          el.setAttribute("data-state", "leaving");
          setTimeout(function () {
            if (el.parentNode) el.parentNode.removeChild(el);
          }, 320);
        }

        function startTimer() {
          startedAt = Date.now();
          timer = setTimeout(dismiss, remaining);
        }

        function pauseTimer() {
          clearTimeout(timer);
          remaining = Math.max(400, remaining - (Date.now() - startedAt));
        }

        el.addEventListener("click", dismiss);
        el.addEventListener("pointerenter", pauseTimer);
        el.addEventListener("pointerleave", startTimer);
        document.addEventListener("visibilitychange", function onVis() {
          if (!el.parentNode) {
            document.removeEventListener("visibilitychange", onVis);
            return;
          }
          if (document.hidden) pauseTimer();
          else startTimer();
        });

        startTimer();
      }

      // 4. Botões de cópia rápida
      document.querySelectorAll("[data-copy-text]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var text = btn.getAttribute("data-copy-text") || "";
          var label = btn.getAttribute("data-copy-label") || "Copiado";
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function () {
              showToast(label);
            }).catch(function () {
              showToast(label);
            });
          } else {
            showToast(label);
          }
        });
      });

      // 5. Tooltips origin-aware: delay inicial na primeira abertura, instantâneos nos hovers subsequentes
      var canHover = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
      if (canHover) {
        var groupActive = false;
        var closeGroupTimer = null;

        document.querySelectorAll(".tip-trigger").forEach(function (trigger) {
          var bubble = trigger.querySelector(".tip-bubble");
          if (!bubble) return;
          var openTimer = null;

          trigger.addEventListener("pointerenter", function () {
            clearTimeout(closeGroupTimer);
            clearTimeout(openTimer);
            if (groupActive) {
              bubble.setAttribute("data-instant", "true");
              bubble.setAttribute("data-open", "true");
            } else {
              bubble.removeAttribute("data-instant");
              openTimer = setTimeout(function () {
                groupActive = true;
                bubble.setAttribute("data-open", "true");
              }, 320);
            }
          });

          trigger.addEventListener("pointerleave", function () {
            clearTimeout(openTimer);
            bubble.setAttribute("data-open", "false");
            closeGroupTimer = setTimeout(function () {
              groupActive = false;
            }, 450);
          });
        });
      }

      // 6. Segmented Control com clip-path para Período (Manhã / Tarde)
      var segmented = document.getElementById("periodo-segmented");
      var periodoInput = document.getElementById("paciente-periodo");
      if (segmented && periodoInput) {
        var options = segmented.querySelectorAll("[data-periodo-opt]");
        options.forEach(function (opt) {
          opt.addEventListener("click", function () {
            var val = opt.getAttribute("data-periodo-opt");
            periodoInput.value = val;
            segmented.setAttribute("data-selected", val);
            options.forEach(function (o) {
              o.setAttribute("aria-checked", o === opt ? "true" : "false");
            });
          });
        });
      }

      // 7. Seleção rápida de procedimento nos cards + destaque sutil + toast
      var procSelect = document.getElementById("paciente-procedimento");
      var nomeInput = document.getElementById("paciente-nome");
      document.querySelectorAll("[data-select-proc]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var proc = btn.getAttribute("data-select-proc");
          if (procSelect && proc) {
            procSelect.value = proc;
            procSelect.classList.add("field-highlight");
            setTimeout(function () {
              procSelect.classList.remove("field-highlight");
            }, 900);
            showToast("Procedimento selecionado: " + proc);
          }
          if (nomeInput) {
            setTimeout(function () { nomeInput.focus(); }, 320);
          }
        });
      });

      // 8. Scroll Reveal (IntersectionObserver, once: true)
      var revealEls = document.querySelectorAll(".reveal-item");
      if ("IntersectionObserver" in window && revealEls.length) {
        var observer = new IntersectionObserver(function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              entry.target.setAttribute("data-visible", "true");
              observer.unobserve(entry.target);
            }
          });
        }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });

        revealEls.forEach(function (el) { observer.observe(el); });
      } else {
        revealEls.forEach(function (el) { el.setAttribute("data-visible", "true"); });
      }

      // 9. Envio do Formulário com transição blur-crossfade no botão
      var form = document.getElementById("form-agendamento");
      var submitLabel = document.getElementById("btn-submit-label");
      var originalLabelHTML = submitLabel ? submitLabel.innerHTML : "";

      if (form) {
        form.addEventListener("submit", function (e) {
          e.preventDefault();
          var nome = document.getElementById("paciente-nome").value.trim();
          var procedimento = document.getElementById("paciente-procedimento").value;
          var periodo = document.getElementById("paciente-periodo").value;

          var mensagem = "Olá! Gostaria de solicitar o agendamento de uma consulta na Unic Clínica.\n\n" +
            "*Nome:* " + nome + "\n" +
            "*Procedimento:* " + procedimento + "\n" +
            "*Período de preferência:* " + periodo;

          var targetPhone = cleanPhone || "5500000000000";
          var url = "https://wa.me/" + targetPhone + "?text=" + encodeURIComponent(mensagem);

          if (submitLabel) {
            submitLabel.setAttribute("data-transitioning", "true");
            setTimeout(function () {
              submitLabel.innerHTML = '<span>Abrindo WhatsApp...</span>';
              submitLabel.setAttribute("data-transitioning", "false");
            }, 140);

            setTimeout(function () {
              submitLabel.setAttribute("data-transitioning", "true");
              setTimeout(function () {
                submitLabel.innerHTML = originalLabelHTML;
                submitLabel.setAttribute("data-transitioning", "false");
              }, 140);
            }, 1800);
          }

          window.open(url, "_blank", "noopener,noreferrer");
        });
      }
    })();
