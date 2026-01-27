
const valorReceita = 1250.75; 
const valorDespesa = 850.50;


function animarValor(elementId, valorFinal, duracao = 1500) {
  const elemento = document.getElementById(elementId);
  let start = 0;
  const passo = valorFinal / (duracao / 30); 

  const contador = setInterval(() => {
    start += passo;
    if (start >= valorFinal) {
      start = valorFinal;
      clearInterval(contador);
    }
    elemento.textContent = "R$ " + start.toLocaleString('pt-BR', { 
      minimumFractionDigits: 2, 
      maximumFractionDigits: 2 
    });
  }, 30);
}


animarValor('saldoReceita', valorReceita);
animarValor('saldoDespesa', valorDespesa);


const ctxReceitas = document.getElementById('graficoReceitas').getContext('2d');
const graficoReceitas = new Chart(ctxReceitas, {
  type: 'line',
  data: {
    labels: [],
    datasets: [{
      label: 'Receitas',
      data: [0, 0, 0, 0, 0], 
      fill: true,
      backgroundColor: 'rgba(91, 43, 224, 0.2)',
      borderColor: 'rgba(91, 43, 224, 1)',
      tension: 0.4,
      pointRadius: 5,
      pointBackgroundColor: 'rgba(91, 43, 224, 1)'
    }]
  },
  options: {
    responsive: true,
    plugins: { legend: { display: true } },
    scales: { y: { beginAtZero: true } }
  }
});


const ctxDespesas = document.getElementById('graficoDespesas').getContext('2d');
const graficoDespesas = new Chart(ctxDespesas, {
  type: 'line',
  data: {
    labels: [],
    datasets: [{
      label: 'Despesas',
      data: [0, 0, 0, 0, 0], 
      fill: true,
      backgroundColor: 'rgba(255, 99, 132, 0.2)',
      borderColor: 'rgba(255, 99, 132, 1)',
      tension: 0.4,
      pointRadius: 5,
      pointBackgroundColor: 'rgba(255, 99, 132, 1)'
    }]
  },
  options: {
    responsive: true,
    plugins: { legend: { display: true } },
    scales: { y: { beginAtZero: true } }
  }
});
