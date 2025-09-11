(function(){
  const $ = (sel) => document.querySelector(sel);

  const form = $("#upload-form");
  const fileInput = $("#file-input");

  const upWrap = $("#upload-wrap");
  const upPct = $("#upload-pct");
  const upBar = $("#upload-bar");

  const prWrap = $("#process-wrap");
  const prCount = $("#proc-count");
  const prTotal = $("#proc-total");
  const prBar = $("#proc-bar");

  const result = $("#result");
  const conclusion = $("#conclusion");
  const chartEl = $("#chart");
  let chart;

  // CSRF
  function getCookie(name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? m.pop() : '';
  }
  const CSRF_TOKEN = getCookie('csrftoken');

  form.addEventListener("submit", function(e){
    e.preventDefault();
    const files = fileInput.files;
    if(!files || !files.length){
      alert("请选择至少一个文件");
      return;
    }

    // reset ui
    upWrap.classList.remove("hidden");
    prWrap.classList.add("hidden");
    result.classList.add("hidden");
    upPct.textContent = "0%";
    upBar.style.width = "0%";

    const fd = new FormData();
    for(let i=0; i<files.length; i++){
      fd.append("files", files[i]);
    }

    const xhr = new XMLHttpRequest();
    xhr.open("POST", window.location.pathname + "upload/");
    xhr.setRequestHeader("X-CSRFToken", CSRF_TOKEN);

    xhr.upload.onprogress = function(evt){
      if(evt.lengthComputable){
        const pct = Math.round(evt.loaded / evt.total * 100);
        upPct.textContent = pct + "%";
        upBar.style.width = pct + "%";
      }
    };

    xhr.onload = function(){
      if(xhr.status !== 200){
        alert("上传失败：" + xhr.status);
        return;
      }
      upWrap.classList.add("hidden");
      const resp = JSON.parse(xhr.responseText);
      const jobId = resp.job_id;
      poll(jobId);
    };

    xhr.onerror = function(){
      alert("上传异常");
    };

    xhr.send(fd);
  });

  function poll(jobId){
    prWrap.classList.remove("hidden");
    prCount.textContent = "0";
    prTotal.textContent = "0";
    prBar.style.width = "0%";

    const url = window.location.pathname + "status/" + jobId + "/";
    const timer = setInterval(async () => {
      try{
        const r = await fetch(url, { headers: { "X-Requested-With": "fetch" }});
        if(!r.ok){
          clearInterval(timer);
          alert("查询失败：" + r.status);
          return;
        }
        const data = await r.json();
        if(data.error){
          clearInterval(timer);
          alert("任务错误：" + data.error);
          return;
        }

        prCount.textContent = data.processed;
        prTotal.textContent = data.total;
        const pct = Math.max(0, Math.min(100, Math.round((data.processed / data.total) * 100)));
        prBar.style.width = pct + "%";

        if(data.status === "done"){
          clearInterval(timer);
          showResult(data.result);
        }else if(data.status === "error"){
          clearInterval(timer);
          alert("处理失败：" + (data.error || "未知错误"));
        }
      }catch(e){
        clearInterval(timer);
        alert("轮询异常：" + e);
      }
    }, 1000);
  }

  function showResult(res){
    if(!res){
      alert("无结果");
      return;
    }
    conclusion.textContent = res.conclusion || "无结论";
    const labels = ["1","2","3","4","5","6","7","8","9"];
    const actual = labels.map(d => (res.actual && res.actual[parseInt(d)]) || 0);
    const expected = labels.map(d => (res.expected && res.expected[parseInt(d)]) || 0);

    if(chart){ chart.destroy(); }
    chart = new Chart(chartEl.getContext("2d"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "实际分布(%)", data: actual, backgroundColor: "rgba(54,162,235,0.5)" },
          { label: "理论分布(%)", data: expected, type: "line", borderColor: "red", fill: false, tension: 0 }
        ]
      },
      options: {
        scales: { y: { beginAtZero: true, suggestedMax: 32 } }
      }
    });

    result.classList.remove("hidden");
  }
})();
