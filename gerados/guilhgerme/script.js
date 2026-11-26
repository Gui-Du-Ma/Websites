(function () {
      var rawPhone = "15988015168";
      var cleanPhone = rawPhone.replace(/\D/g, "");
      if (cleanPhone.length >= 10 && cleanPhone.length <= 11 && !cleanPhone.startsWith("55")) {
        cleanPhone = "55" + cleanPhone;
      }

      var directLinks = document.querySelectorAll("[data-wa-direct]");
      directLinks.forEach(function (link) {
        if (cleanPhone) {
          var defaultMsg = encodeURIComponent("Olá! Gostaria de informações sobre agendamento de consulta na " + "guilhgerme" + ".");
          link.setAttribute("href", "https://wa.me/" + cleanPhone + "?text=" + defaultMsg);
          link.setAttribute("target", "_blank");
          link.setAttribute("rel", "noopener noreferrer");
        }
      });

      var procSelect = document.getElementById("paciente-procedimento");
      var nomeInput = document.getElementById("paciente-nome");
      document.querySelectorAll("[data-select-proc]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var proc = btn.getAttribute("data-select-proc");
          if (procSelect && proc) {
            procSelect.value = proc;
          }
          if (nomeInput) {
            setTimeout(function () { nomeInput.focus(); }, 300);
          }
        });
      });

      var form = document.getElementById("form-agendamento");
      if (form) {
        form.addEventListener("submit", function (e) {
          e.preventDefault();
          var nome = document.getElementById("paciente-nome").value.trim();
          var procedimento = document.getElementById("paciente-procedimento").value;
          var periodo = document.getElementById("paciente-periodo").value;

          var mensagem = "Olá! Gostaria de solicitar o agendamento de uma consulta na guilhgerme.\n\n" +
            "*Nome:* " + nome + "\n" +
            "*Procedimento:* " + procedimento + "\n" +
            "*Período de preferência:* " + periodo;

          var targetPhone = cleanPhone || "5500000000000";
          var url = "https://wa.me/" + targetPhone + "?text=" + encodeURIComponent(mensagem);
          window.open(url, "_blank", "noopener,noreferrer");
        });
      }
    })();
