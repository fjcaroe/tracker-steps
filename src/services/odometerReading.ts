/** Explicit physical readings: avoid treating Chilean thousands as decimals. */
export function parseOdometerReading(input:string){
 const value=input.trim();
 if(!/^\d+(?:[.,]\d{1,2})?$/.test(value))throw new Error('Escribe la lectura sin separadores de miles. Ejemplo: 123456,5.');
 const result=Number(value.replace(',','.'));
 if(!Number.isFinite(result)||result<0)throw new Error('La lectura debe ser un número igual o mayor que cero.');
 return result;
}
