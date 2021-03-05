# FAT32 редактор

## Описание
Данная программа читает файл с образом раздела с файловой системой FAT32 и позволяет читать файлы и просматривать директории, находящиеся в образе.


## Использование
* Для чтения и/или редактирования образа: 'main.py <файл с образом>'
* Для сканирования: 'main.py \[-s] \[-i] \[-l] \[-z] <файл с образом>', где 
    * -s обычное сканирование
    * -i сканирование + поиск и устранение пересекающихся цепочек кластеров
    * -l сканирование + поиск и освобождение потерянных кластеров
    * -z сканирование + поиск и исправление ошибок, связанных с неверно указанным размером файла
    
