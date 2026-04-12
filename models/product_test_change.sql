SELECT
    ProductID,
    Name,
    ProductNumber,
    ListPrice,
    ListPrice * 10.0 AS PriceIncreased
FROM Production.Product
WHERE ListPrice IS NOT NULL
